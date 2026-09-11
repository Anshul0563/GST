from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re
from collections import Counter

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    clean_column,
    excel_frames,
    finalize_period_transaction,
    first_value,
    belongs_to_period,
    money,
    parse_date,
    should_skip_transaction,
    text,
)


RETURN_DATE_ALIASES = [
    "cancel return date",
    "return date",
    "credit note date",
]
RETURN_TYPE_ALIASES = ["transaction type", "type", "document type", "doc_type"]
METADATA_TYPE_ALIASES = ["type", "document type", "doc_type"]
METADATA_INVOICE_ALIASES = [
    "invoice no.",
    "invoice no",
    "invoice number",
    "tax invoice no",
]


def source_kind(path: Path, frames: list[tuple[str, object]]) -> str:
    """Identify Meesho exports from their columns, with a generic filename fallback."""
    columns = {
        clean_column(column)
        for _, frame in frames
        for column in getattr(frame, "columns", [])
    }
    has_financial_columns = any(
        clean_column(alias) in columns
        for aliases in SOURCE_TOTAL_FIELDS.values()
        for alias in aliases
    )
    has_invoice_metadata = (
        any(clean_column(alias) in columns for alias in METADATA_TYPE_ALIASES)
        and any(clean_column(alias) in columns for alias in SUBORDER_ALIASES)
        and any(clean_column(alias) in columns for alias in METADATA_INVOICE_ALIASES)
        and not has_financial_columns
    )
    if has_invoice_metadata:
        return "metadata"
    if any(clean_column(alias) in columns for alias in RETURN_DATE_ALIASES):
        return "returns"
    stem = clean_column(path.stem)
    if any(marker in stem for marker in ("return", "refund", "credit")):
        return "returns"
    return "sales"


def row_is_return(row: dict) -> bool:
    if first_value(row, RETURN_DATE_ALIASES) not in (None, ""):
        return True
    raw_type = text(first_value(row, RETURN_TYPE_ALIASES))
    if raw_type:
        normalized = raw_type.lower()
        return any(marker in normalized for marker in ("return", "refund", "credit"))
    return False
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


def report_period_date(row: dict) -> object | None:
    report_date = first_value(
        row,
        [
            "manifest date",
            "transaction date",
            "report date",
        ],
    )
    if text(report_date):
        return report_date

    # Meesho can include a cancellation/adjustment in the monthly TCS
    # report even when its order date belongs to the previous month. In
    # that case the report's financial year/month fields are the period
    # authority, not the order date.
    raw_year = text(first_value(row, ["financial year", "fy", "financial year name"]))
    raw_month = text(first_value(row, ["month number", "month", "report month"]))
    if not raw_year or not raw_month:
        return None

    year_matches = re.findall(r"\d{4}", raw_year)
    if not year_matches:
        return None
    financial_year = int(year_matches[0])

    month_number: int | None = None
    if raw_month.isdigit():
        month_number = int(raw_month)
    else:
        for pattern in ("%B", "%b"):
            try:
                month_number = datetime.strptime(raw_month.strip(), pattern).month
                break
            except ValueError:
                continue
    if month_number is None or not 1 <= month_number <= 12:
        return None

    # Meesho's financial year is April to March. For labels such as
    # 2026-27, January to March belongs to the second calendar year.
    if len(year_matches) > 1 and month_number <= 3:
        financial_year = int(year_matches[1])
    elif len(year_matches) == 1 and month_number <= 3 and raw_year != str(financial_year):
        financial_year += 1
    return f"{financial_year:04d}-{month_number:02d}-01"


def align_sale_date_to_report_period(row: dict, filing_period: str) -> None:
    invoice_date = first_value(row, ["invoice date", "invoice_date"])
    order_date = first_value(row, ["order date", "date"])
    source_date = invoice_date or order_date
    period_date = report_period_date(row)
    if (
        source_date not in (None, "")
        and period_date not in (None, "")
        and not belongs_to_period(source_date, filing_period)
        and belongs_to_period(period_date, filing_period)
    ):
        row["invoice date"] = period_date


def metadata_doc_type(raw_type: str) -> str | None:
    normalized = raw_type.strip().lower().replace(" ", "_")
    if normalized == "invoice":
        return "invoice"
    if normalized in {"credit_note", "credit_discount", "credit_conversion"}:
        return "credit_note"
    return None


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

        loaded_frames: list[tuple[Path, str, object, str]] = []
        financial_source_files: set[str] = set()
        metadata_by_suborder: dict[str, dict[str, dict[str, object]]] = {}
        metadata_documents: list[dict[str, object]] = []
        etin_by_suborder: dict[str, str] = {}
        report_etins: set[str] = set()
        source_totals = {
            "taxable_value": Decimal("0"),
            "total_tax": Decimal("0"),
            "gross_amount": Decimal("0"),
        }
        source_breakdown = {
            "sales": {key: Decimal("0") for key in source_totals},
            "returns": {key: Decimal("0") for key in source_totals},
        }
        source_period_counts: Counter[str] = Counter()

        for path in files:
            try:
                frames = excel_frames(path)
                kind = source_kind(path, frames)
                if kind != "metadata":
                    financial_source_files.add(path.name)

                # First pass → metadata collect
                for _, frame in frames:
                    for _, series in frame.iterrows():
                        row = series.to_dict()

                        suborder = suborder_key(row)
                        if not suborder:
                            continue

                        raw_etin = text(
                            first_value(
                                row,
                                [
                                    "eco tcs gstin",
                                    "ecommerce gstin",
                                    "operator gstin",
                                ],
                            )
                        )
                        if raw_etin:
                            etin = raw_etin.upper()
                            etin_by_suborder[suborder] = etin
                            report_etins.add(etin)

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
                        invoice_no = first_value(
                            row,
                            [
                                "invoice no.",
                                "invoice no",
                                "invoice number",
                                "tax invoice no",
                            ],
                        )
                        doc_type_for_issue = metadata_doc_type(raw_type)
                        if doc_type_for_issue and invoice_no not in (None, ""):
                            metadata_documents.append(
                                {
                                    "doc_type": doc_type_for_issue,
                                    "invoice_no": text(invoice_no),
                                    "suborder": suborder,
                                    "source_file": f"{path.name}:{sheet_name}",
                                    "invoice_date": first_value(
                                        row,
                                        [
                                            "invoice date",
                                            "order date",
                                            "document date",
                                        ],
                                    ),
                                }
                            )

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
                    loaded_frames.append((path, sheet_name, frame, kind))

            except Exception as exc:
                result.errors.append(
                    {
                        "file": path.name,
                        "error": str(exc),
                    }
                )

        # Second pass → transaction creation
        for path, sheet_name, frame, kind in loaded_frames:
            for index, series in frame.iterrows():
                row = series.to_dict()

                if not has_financial_values(row):
                    continue

                suborder = suborder_key(row)

                report_date = parse_date(report_period_date(row))
                if report_date:
                    source_period_counts[
                        f"{report_date.month:02d}{report_date.year}"
                    ] += 1

                is_return = kind == "returns" or row_is_return(row)

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
                else:
                    align_sale_date_to_report_period(row, self.filing_period)

                row["doc_type"] = "credit_note" if is_return else "invoice"
                source_etin = text(
                    first_value(
                        row,
                        [
                            "eco tcs gstin",
                            "ecommerce gstin",
                            "operator gstin",
                        ],
                    )
                )
                if source_etin:
                    row["etin"] = source_etin.upper()

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
                breakdown = source_breakdown["returns" if is_return else "sales"]
                for field in source_totals:
                    source_value = signed_source_amount(row, field, is_return)
                    breakdown[field] += abs(source_value) if is_return else source_value
                result.transactions.append(finalized)

        existing_documents = {
            (
                str(txn.get("doc_type") or "").lower(),
                str(txn.get("invoice_no") or "").strip(),
            )
            for txn in result.transactions
            if txn.get("invoice_no")
        }
        for document in metadata_documents:
            key = (
                str(document.get("doc_type") or "").lower(),
                str(document.get("invoice_no") or "").strip(),
            )
            if not key[0] or not key[1] or key in existing_documents:
                continue
            document_date = parse_date(document.get("invoice_date"))
            document_etin = etin_by_suborder.get(str(document.get("suborder") or ""))
            if document_etin is None and len(report_etins) == 1:
                document_etin = next(iter(report_etins))
            result.transactions.append(
                {
                    "platform": self.platform,
                    "gstin": self.gstin,
                    "etin": document_etin,
                    "filing_period": self.filing_period,
                    "order_id": None,
                    "order_item_id": None,
                    "invoice_no": key[1],
                    "invoice_date": document_date,
                    "document_date": document_date,
                    "doc_type": key[0],
                    "buyer_state_code": None,
                    "buyer_state_name": None,
                    "hsn": None,
                    "product_name": None,
                    "sku": None,
                    "qty": Decimal("0.00"),
                    "taxable_value": Decimal("0.00"),
                    "gst_rate": Decimal("0.00"),
                    "igst": Decimal("0.00"),
                    "cgst": Decimal("0.00"),
                    "sgst": Decimal("0.00"),
                    "cess": Decimal("0.00"),
                    "tcs": Decimal("0.00"),
                    "tds": Decimal("0.00"),
                    "gross_amount": Decimal("0.00"),
                    "discount_seller": Decimal("0.00"),
                    "discount_platform": Decimal("0.00"),
                    "settlement_amount": Decimal("0.00"),
                    "source_file": document.get("source_file") or "metadata",
                    "raw_row_json": None,
                    "validation_status": "skipped",
                    "validation_errors": "Document issue metadata row",
                }
            )
            existing_documents.add(key)

        reconcile_source_totals(result, source_totals)

        result.debug["meesho_metadata_rows"] = len(metadata_by_suborder)
        financial_transactions = [
            txn
            for txn in result.transactions
            if str(txn.get("source_file") or "").split(":", 1)[0]
            in financial_source_files
        ]
        metadata_only_transactions = [
            txn for txn in result.transactions if txn not in financial_transactions
        ]
        result.debug["meesho_financial_rows"] = len(financial_transactions)
        result.debug["meesho_metadata_only_rows"] = len(metadata_only_transactions)
        result.debug["meesho_total_result_rows"] = len(result.transactions)
        result.debug["meesho_source_breakdown"] = {
            category: {
                field: str(round_money(value))
                for field, value in totals.items()
            }
            for category, totals in source_breakdown.items()
        }
        result.debug["meesho_document_issue_rows"] = len(result.transactions)
        result.debug["meesho_source_periods"] = dict(source_period_counts)
        if source_period_counts:
            result.debug["meesho_dominant_period"] = source_period_counts.most_common(1)[0][0]
            result.debug["source_periods"] = dict(source_period_counts)
            result.debug["source_dominant_period"] = source_period_counts.most_common(1)[0][0]

        return result
