from pathlib import Path
from decimal import Decimal, InvalidOperation

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    excel_frames,
    finalize_period_transaction,
    first_value,
    money,
    should_skip_transaction,
    text,
)
from app.services.validation import round_money, validate_transaction
from app.services.pos_resolver import (
    new_pos_debug,
    observe_pos_debug,
    resolve_pos,
)

SUBORDER_ALIASES = [
    "suborder no.",
    "sub order num",
    "suborder number",
    "sub order number",
    "sub order no",
    "order id",
]


def suborder_key(row: dict) -> str | None:
    return text(first_value(row, SUBORDER_ALIASES))


def has_financial_values(row: dict) -> bool:
    fields = [
        "total taxable sale value",
        "taxable value",
        "taxable amount",
        "tax amount",
        "total invoice value",
        "invoice amount",
        "gross amount",
    ]
    return any(money(first_value(row, [field])) != 0 for field in fields)


def is_empty(value: object) -> bool:
    return text(value) is None


SOURCE_TOTAL_FIELDS = {
    "taxable_value": [
        "total taxable sale value",
        "taxable value",
        "taxable amount",
    ],
    "total_tax": [
        "tax amount",
        "total tax amount",
        "gst amount",
    ],
    "gross_amount": [
        "total invoice value",
        "invoice amount",
        "gross amount",
    ],
}


def precise_amount(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    cleaned = str(value).replace(",", "").replace("₹", "").replace("%", "").strip()
    if cleaned.lower() in {"", "-", "nan", "none", "null"}:
        return Decimal("0")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")
    return -amount if negative else amount


def signed_source_amount(row: dict, field: str, is_return: bool) -> Decimal:
    amount = precise_amount(first_value(row, SOURCE_TOTAL_FIELDS[field]))
    return -abs(amount) if is_return else amount


def refresh_validation(txn: dict) -> None:
    errors = validate_transaction(txn)
    zero_only = errors and all(
        error in {"Zero amount row", "Zero rate and zero taxable row"}
        for error in errors
    )
    txn["validation_status"] = "skipped" if zero_only else "invalid" if errors else "valid"
    txn["validation_errors"] = "; ".join(errors) if errors else None


def add_total_tax_delta(txn: dict, delta: Decimal) -> None:
    if delta == Decimal("0.00"):
        return
    if money(txn.get("igst")) != Decimal("0.00"):
        txn["igst"] = money(txn.get("igst")) + delta
        return
    half = round_money(delta / Decimal("2"))
    txn["cgst"] = money(txn.get("cgst")) + half
    txn["sgst"] = money(txn.get("sgst")) + (delta - half)


def reconcile_source_totals(result: ParseResult, source_totals: dict[str, Decimal]) -> None:
    if not result.transactions:
        return
    actual_taxable = sum(
        (money(txn.get("taxable_value")) for txn in result.transactions),
        Decimal("0.00"),
    )
    actual_tax = sum(
        (
            money(txn.get("igst"))
            + money(txn.get("cgst"))
            + money(txn.get("sgst"))
            + money(txn.get("cess"))
            for txn in result.transactions
        ),
        Decimal("0.00"),
    )
    actual_gross = sum(
        (money(txn.get("gross_amount")) for txn in result.transactions),
        Decimal("0.00"),
    )
    expected = {key: round_money(value) for key, value in source_totals.items()}
    deltas = {
        "taxable_value": expected["taxable_value"] - actual_taxable,
        "total_tax": expected["total_tax"] - actual_tax,
        "gross_amount": expected["gross_amount"] - actual_gross,
    }
    if not any(deltas.values()):
        return

    adjustable = next(
        (
            txn
            for txn in reversed(result.transactions)
            if money(txn.get("taxable_value")) != Decimal("0.00")
            or money(txn.get("igst")) + money(txn.get("cgst")) + money(txn.get("sgst"))
            != Decimal("0.00")
        ),
        result.transactions[-1],
    )
    if abs(deltas["taxable_value"]) <= Decimal("1.00"):
        adjustable["taxable_value"] = money(adjustable.get("taxable_value")) + deltas["taxable_value"]
    if abs(deltas["total_tax"]) <= Decimal("1.00"):
        add_total_tax_delta(adjustable, deltas["total_tax"])
    if abs(deltas["gross_amount"]) <= Decimal("1.00"):
        adjustable["gross_amount"] = money(adjustable.get("gross_amount")) + deltas["gross_amount"]
    refresh_validation(adjustable)
    result.debug["source_total_reconciliation"] = {
        "expected": {key: str(value) for key, value in expected.items()},
        "actual_before": {
            "taxable_value": str(actual_taxable),
            "total_tax": str(actual_tax),
            "gross_amount": str(actual_gross),
        },
        "deltas_applied": {key: str(value) for key, value in deltas.items()},
        "adjusted_invoice_no": adjustable.get("invoice_no"),
        "adjusted_order_item_id": adjustable.get("order_item_id"),
    }


class MeeshoParser(MarketplaceParser):
    platform = "meesho"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)

        loaded_frames: list[tuple[Path, str, object]] = []
        metadata_by_suborder: dict[str, dict[str, dict[str, object]]] = {}
        source_totals = {
            "taxable_value": Decimal("0"),
            "total_tax": Decimal("0"),
            "gross_amount": Decimal("0"),
        }

        for path in files:
            try:
                frames = excel_frames(path)

                # First pass → metadata collect
                for _, frame in frames:
                    for _, series in frame.iterrows():
                        row = series.to_dict()

                        suborder = suborder_key(row)
                        if not suborder:
                            continue

                        raw_type = str(
                            first_value(
                                row,
                                [
                                    "type",
                                    "doc_type",
                                    "document type",
                                    "transaction type",
                                ],
                            )
                            or ""
                        ).lower()

                        metadata_type = (
                            "credit_note"
                            if (
                                "credit" in raw_type
                                or "return" in raw_type
                                or "refund" in raw_type
                            )
                            else "invoice"
                        )

                        metadata = metadata_by_suborder.setdefault(
                            suborder,
                            {},
                        ).setdefault(metadata_type, {})

                        values = {
                            "invoice no": first_value(
                                row,
                                [
                                    "invoice no.",
                                    "invoice no",
                                    "invoice number",
                                    "tax invoice no",
                                ],
                            ),
                            "invoice date": first_value(
                                row,
                                [
                                    "invoice date",
                                    "order date",
                                ],
                            ),
                            "hsn": first_value(
                                row,
                                [
                                    "hsn",
                                    "hsn code",
                                    "hsn/sac",
                                ],
                            ),
                            "product description": first_value(
                                row,
                                [
                                    "product description",
                                    "product name",
                                    "product title",
                                    "item description",
                                ],
                            ),
                            "end customer state new": first_value(
                                row,
                                [
                                    "end customer state new",
                                    "customer state",
                                    "delivery state",
                                    "shipping state",
                                    "recipient state",
                                    "buyer state",
                                    "place of supply",
                                    "pos",
                                    "state",
                                ],
                            ),
                        }

                        for key, value in values.items():
                            if value not in (None, ""):
                                metadata[key] = value

                # Store all frames for second pass
                for sheet_name, frame in frames:
                    loaded_frames.append((path, sheet_name, frame))

            except Exception as exc:
                result.errors.append(
                    {
                        "file": path.name,
                        "error": str(exc),
                    }
                )

        # Second pass → transaction creation
        for path, sheet_name, frame in loaded_frames:
            for index, series in frame.iterrows():
                row = series.to_dict()

                if not has_financial_values(row):
                    continue

                suborder = suborder_key(row)

                is_return = "return" in path.name.lower() or first_value(
                    row,
                    [
                        "cancel return date",
                        "return date",
                    ],
                ) not in (None, "")

                metadata_type = "credit_note" if is_return else "invoice"

                metadata = metadata_by_suborder.get(suborder or "", {}).get(
                    metadata_type, {}
                )

                # Fill missing metadata
                for key, value in metadata.items():
                    if is_empty(row.get(key)):
                        row[key] = value

                # Invoice fallback
                if metadata.get("invoice no") and not first_value(
                    row,
                    [
                        "invoice no.",
                        "invoice no",
                        "invoice number",
                        "tax invoice no",
                    ],
                ):
                    row["invoice no"] = metadata["invoice no"]
                elif suborder and not first_value(
                    row,
                    [
                        "invoice no.",
                        "invoice no",
                        "invoice number",
                        "tax invoice no",
                    ],
                ):
                    row["invoice no"] = suborder

                # State fallback
                if metadata.get("end customer state new") and not first_value(
                    row,
                    [
                        "end customer state new",
                        "customer state",
                        "delivery state",
                        "shipping state",
                        "recipient state",
                        "buyer state",
                        "place of supply",
                        "pos",
                        "state",
                    ],
                ):
                    row["resolved state"] = metadata["end customer state new"]

                if is_return:
                    return_date = first_value(
                        row,
                        [
                            "cancel return date",
                            "return date",
                            "credit note date",
                            "document date",
                        ],
                    )
                    if return_date not in (None, ""):
                        row["credit note date"] = return_date
                        row["invoice date"] = return_date

                row["doc_type"] = "credit_note" if is_return else "invoice"

                txn = self.normalize_row(
                    row,
                    f"{path.name}:{sheet_name}",
                )
                if not is_return:
                    txn["_preserve_source_sign"] = True

                if not txn.get("invoice_no"):
                    result.errors.append(
                        {
                            "file": path.name,
                            "sheet": sheet_name,
                            "row": int(index) + 2,
                            "suborder": suborder,
                            "error": "Missing Meesho invoice metadata; row excluded",
                        }
                    )
                    continue

                observe_pos_debug(
                    result.debug,
                    int(index) + 2,
                    resolve_pos(row, txn, self.platform),
                    row,
                )

                if should_skip_transaction(txn):
                    continue

                finalized = finalize_period_transaction(
                    result,
                    txn,
                    source_file=path.name,
                    sheet_name=sheet_name,
                    row_number=int(index) + 2,
                )
                if finalized is None:
                    continue

                source_totals["taxable_value"] += signed_source_amount(
                    row,
                    "taxable_value",
                    is_return,
                )
                source_totals["total_tax"] += signed_source_amount(
                    row,
                    "total_tax",
                    is_return,
                )
                source_totals["gross_amount"] += signed_source_amount(
                    row,
                    "gross_amount",
                    is_return,
                )
                result.transactions.append(finalized)

        reconcile_source_totals(result, source_totals)

        result.debug["meesho_metadata_rows"] = len(metadata_by_suborder)

        result.debug["meesho_financial_rows"] = len(result.transactions)

        return result
