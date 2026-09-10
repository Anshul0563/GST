from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    clean_column,
    first_value,
    parse_date,
    raw_frames,
    text,
    unique_headers,
)
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money, validate_gstin

SHEET_5B = "Section 5B in GSTR-1"
SHEET_7A = "Section 7(A)(2) in GSTR-1"
SHEET_7B = "Section 7(B)(2) in GSTR-1"
SHEET_12 = "Section 12 in GSTR-1"
SHEET_GSTR8 = "Section 3 in GSTR-8"
SHEET_SERIES = "Invoice Series"

GSTR8_HEADERS = {
    "gstin of seller",
    "seller code",
    "tcs gstin of snapdeal",
    "gross taxable value",
    "taxable sales return value",
    "net taxable value",
    "tcs %",
    "tcs igst amount",
    "tcs cgst amount",
    "tcs sgst amount",
    "igst amount",
    "cgst amount",
    "sgst amount",
}

REQUIRED_HEADERS = {
    SHEET_5B: {
        "tcs gstin of snapdeal",
        "gstin of seller",
        "delivered state",
        "sub order no",
        "invoice number",
        "order invoice date",
        "invoice amount",
        "igst %",
        "taxable amount",
        "igst amount",
        "cess %",
        "cess amount",
    },
    SHEET_7A: {
        "tcs gstin of snapdeal",
        "gstin of seller",
        "gross taxable value",
        "taxable sales return value",
        "aggregate taxable value",
        "cgst %",
        "cgst amount",
        "sgst/ut %",
        "sgst/ut amount",
        "cess %",
        "cess amount",
    },
    SHEET_7B: {
        "tcs gstin of snapdeal",
        "delivered state",
        "gstin of seller",
        "gross taxable value",
        "taxable sales return value",
        "aggregate taxable value",
        "igst %",
        "igst amount",
        "cess %",
        "cess amount",
    },
    SHEET_12: {
        "gstin of seller",
        "hsn number",
        "total quantity",
        "total value",
        "total taxable value",
        "igst amount",
        "cgst amount",
        "sgst amount",
        "cess amount",
    },
    SHEET_SERIES: {
        "trx type",
        "gstin",
        "invoice series from",
        "invoice series to",
        "total number of invoices",
        "cancelled if any",
        "net invoice issued",
    },
}


def _decimal(value: Any, field: str, row_number: int) -> Decimal:
    if value is None or str(value).strip().lower() in {"", "nan", "none", "null"}:
        raise ValueError(f"Missing numeric value for '{field}' at row {row_number}")
    cleaned = str(value).replace(",", "").replace("₹", "").replace("%", "").strip()
    try:
        return money(Decimal(cleaned))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Invalid numeric value for '{field}' at row {row_number}"
        ) from exc


def _headers(frame) -> tuple[list[str], Any]:
    if frame.dropna(how="all").empty:
        return [], frame
    headers = unique_headers(
        [
            clean_column(value) or f"column {index}"
            for index, value in enumerate(frame.iloc[0].tolist())
        ]
    )
    data = frame.iloc[1:].copy()
    data.columns = headers
    return headers, data.dropna(how="all")


def _require_headers(sheet_name: str, headers: list[str]) -> None:
    required = REQUIRED_HEADERS.get(sheet_name, set())
    missing = sorted(required - set(headers))
    if missing:
        raise ValueError(
            f"Unsupported Snapdeal GST report format: missing column(s) {', '.join(repr(item) for item in missing)} in {sheet_name}"
        )


def _require_header_set(sheet_name: str, headers: list[str], required: set[str]) -> None:
    missing = sorted(required - set(headers))
    if missing:
        raise ValueError(
            f"Unsupported Snapdeal GST report format: missing column(s) "
            f"{', '.join(repr(item) for item in missing)} in {sheet_name}"
        )


def _gstin(
    row: dict[str, Any], field_names: list[str], sheet: str, row_number: int
) -> str:
    value = text(first_value(row, field_names))
    if not value or not validate_gstin(value):
        raise ValueError(f"Invalid GSTIN in {sheet} at row {row_number}")
    return value.upper()


def _rate(value: Any, field: str, row_number: int) -> Decimal:
    rate = _decimal(value, field, row_number)
    if rate < 0 or rate > 100:
        raise ValueError(f"Invalid tax rate for '{field}' at row {row_number}")
    return rate


class SnapdealParser(MarketplaceParser):
    platform = "snapdeal"

    def _base_transaction(
        self,
        *,
        seller_gstin: str,
        etin: str,
        row_number: int,
        sheet: str,
        source_file: str,
    ) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "gstin": self.gstin,
            "etin": etin,
            "filing_period": self.filing_period,
            "source_file": source_file,
            "_snapdeal_source_sheet": sheet,
            "_snapdeal_source_row": row_number,
            "_preserve_source_tax_split": True,
            "_preserve_source_sign": True,
            "_exclude_doc_issue": True,
            "seller_gstin": seller_gstin,
        }

    def _validate_seller(self, seller_gstin: str, sheet: str, row_number: int) -> None:
        if seller_gstin != self.gstin:
            raise ValueError(
                f"Snapdeal report GSTIN mismatch in {sheet} at row {row_number}: "
                f"report has {seller_gstin}, selected profile has {self.gstin}"
            )

    def _record_source_totals(
        self, result: ParseResult, sheet: str, txn: dict[str, Any]
    ) -> None:
        totals = result.debug.setdefault("source_totals", {}).setdefault(
            sheet,
            {
                field: Decimal("0.00")
                for field in ("taxable_value", "igst", "cgst", "sgst", "cess")
            },
        )
        for field in totals:
            totals[field] += money(txn.get(field))

    def _record_aggregate_source(
        self, result: ParseResult, sheet: str, row: dict[str, Any], row_number: int
    ) -> None:
        totals = result.debug.setdefault("source_reconciliation", {}).setdefault(
            sheet,
            {
                "rows": 0,
                "gross_taxable_value": Decimal("0.00"),
                "taxable_sales_return_value": Decimal("0.00"),
                "aggregate_taxable_value": Decimal("0.00"),
                "igst": Decimal("0.00"),
                "cgst": Decimal("0.00"),
                "sgst": Decimal("0.00"),
                "cess": Decimal("0.00"),
            },
        )
        gross = _decimal(
            first_value(row, ["gross taxable value"]),
            "gross taxable value",
            row_number,
        )
        returns = _decimal(
            first_value(row, ["taxable sales return value"]),
            "taxable sales return value",
            row_number,
        )
        aggregate = _decimal(
            first_value(row, ["aggregate taxable value"]),
            "aggregate taxable value",
            row_number,
        )
        totals["rows"] += 1
        totals["gross_taxable_value"] += gross
        totals["taxable_sales_return_value"] += returns
        totals["aggregate_taxable_value"] += aggregate
        for field, names in {
            "igst": ["igst amount"],
            "cgst": ["cgst amount"],
            "sgst": ["sgst/ut amount"],
            "cess": ["cess amount"],
        }.items():
            value = first_value(row, names)
            if value not in (None, ""):
                totals[field] += _decimal(value, names[0], row_number)

        expected = gross - abs(returns)
        if abs(aggregate - expected) > Decimal("0.02"):
            result.debug.setdefault("warnings", []).append(
                {
                    "sheet": sheet,
                    "row": row_number,
                    "type": "aggregate_taxable_mismatch",
                    "gross_minus_return": str(expected),
                    "source_aggregate": str(aggregate),
                }
            )

    def _validate_tax_amount(
        self,
        result: ParseResult,
        *,
        sheet: str,
        row_number: int,
        taxable: Decimal,
        rate: Decimal,
        actual: Decimal,
        field: str,
    ) -> None:
        expected = money(taxable * rate / Decimal("100"))
        if abs(expected - actual) > Decimal("0.02"):
            result.debug.setdefault("warnings", []).append(
                {
                    "sheet": sheet,
                    "row": row_number,
                    "type": "source_tax_mismatch",
                    "field": field,
                    "expected_from_rate": str(expected),
                    "source_amount": str(actual),
                }
            )

    def _source_key(self, sheet: str, txn: dict[str, Any]) -> tuple[Any, ...]:
        if sheet == SHEET_5B:
            return (sheet, txn.get("invoice_no"))
        return (
            sheet,
            txn.get("buyer_state_code"),
            txn.get("taxable_value"),
            txn.get("gst_rate"),
            txn.get("igst"),
            txn.get("cgst"),
            txn.get("sgst"),
            txn.get("cess"),
        )

    def _parse_5b(
        self,
        row: dict[str, Any],
        row_number: int,
        source_file: str,
    ) -> dict[str, Any]:
        seller = _gstin(row, ["gstin of seller"], SHEET_5B, row_number)
        self._validate_seller(seller, SHEET_5B, row_number)
        etin = _gstin(row, ["tcs gstin of snapdeal"], SHEET_5B, row_number)
        pos = text(first_value(row, ["delivered state"]))
        if not pos or not pos.isdigit() or len(pos) != 2:
            raise ValueError(
                f"Invalid delivered state in {SHEET_5B} at row {row_number}"
            )
        invoice_no = text(first_value(row, ["invoice number"]))
        sub_order_no = text(first_value(row, ["sub order no", "suborder no"]))
        invoice_date = parse_date(first_value(row, ["order invoice date"]))
        if not invoice_no:
            raise ValueError(
                f"Missing invoice number in {SHEET_5B} at row {row_number}"
            )
        if invoice_date is None:
            raise ValueError(f"Invalid invoice date in {SHEET_5B} at row {row_number}")
        taxable = _decimal(
            first_value(row, ["taxable amount"]), "taxable amount", row_number
        )
        igst = _decimal(first_value(row, ["igst amount"]), "igst amount", row_number)
        cess = _decimal(first_value(row, ["cess amount"]), "cess amount", row_number)
        txn = self._base_transaction(
            seller_gstin=seller,
            etin=etin,
            row_number=row_number,
            sheet=SHEET_5B,
            source_file=source_file,
        )
        txn["raw_row_json"] = json.dumps(row, default=str)
        txn.update(
            {
                "invoice_no": invoice_no,
                "order_id": sub_order_no,
                "order_item_id": sub_order_no,
                "invoice_date": invoice_date,
                "document_date": invoice_date,
                "doc_type": "invoice",
                "buyer_state_code": pos,
                "buyer_state_name": pos,
                "qty": Decimal("1"),
                "taxable_value": taxable,
                "gst_rate": _rate(first_value(row, ["igst %"]), "igst %", row_number),
                "igst": igst,
                "cgst": Decimal("0.00"),
                "sgst": Decimal("0.00"),
                "cess": cess,
                "gross_amount": _decimal(
                    first_value(row, ["invoice amount"]), "invoice amount", row_number
                ),
            }
        )
        return txn

    def _parse_aggregate(
        self,
        row: dict[str, Any],
        row_number: int,
        sheet: str,
        intra: bool,
        source_file: str,
    ) -> dict[str, Any]:
        seller = _gstin(row, ["gstin of seller"], sheet, row_number)
        self._validate_seller(seller, sheet, row_number)
        etin = _gstin(row, ["tcs gstin of snapdeal"], sheet, row_number)
        pos = seller[:2] if intra else text(first_value(row, ["delivered state"]))
        if not pos or not pos.isdigit() or len(pos) != 2:
            raise ValueError(f"Invalid delivered state in {sheet} at row {row_number}")
        net = _decimal(
            first_value(row, ["aggregate taxable value"]),
            "aggregate taxable value",
            row_number,
        )
        invoice_date = date(int(self.filing_period[2:]), int(self.filing_period[:2]), 1)
        txn = self._base_transaction(
            seller_gstin=seller,
            etin=etin,
            row_number=row_number,
            sheet=sheet,
            source_file=source_file,
        )
        txn["raw_row_json"] = json.dumps(row, default=str)
        txn.update(
            {
                "invoice_no": f"SNAPDEAL-{sheet.split()[1]}-{row_number}",
                "invoice_date": invoice_date,
                "document_date": invoice_date,
                "doc_type": "invoice",
                "buyer_state_code": pos,
                "buyer_state_name": pos,
                "qty": Decimal("0"),
                "taxable_value": net,
                "gst_rate": (
                    _rate(first_value(row, ["igst %"]), "igst %", row_number)
                    if not intra
                    else _rate(
                        _decimal(first_value(row, ["cgst %"]), "cgst %", row_number)
                        + _decimal(
                            first_value(row, ["sgst/ut %"]),
                            "sgst/ut %",
                            row_number,
                        ),
                        "total tax rate",
                        row_number,
                    )
                ),
                "igst": (
                    _decimal(
                        first_value(row, ["igst amount"]), "igst amount", row_number
                    )
                    if not intra
                    else Decimal("0.00")
                ),
                "cgst": (
                    _decimal(
                        first_value(row, ["cgst amount"]), "cgst amount", row_number
                    )
                    if intra
                    else Decimal("0.00")
                ),
                "sgst": (
                    _decimal(
                        first_value(row, ["sgst/ut amount"]),
                        "sgst/ut amount",
                        row_number,
                    )
                    if intra
                    else Decimal("0.00")
                ),
                "cess": _decimal(
                    first_value(row, ["cess amount"]), "cess amount", row_number
                ),
                "gross_amount": _decimal(
                    first_value(row, ["gross taxable value"]),
                    "gross taxable value",
                    row_number,
                ),
            }
        )
        return txn

    def _parse_hsn(
        self, row: dict[str, Any], row_number: int, result: ParseResult
    ) -> None:
        seller = _gstin(row, ["gstin of seller"], SHEET_12, row_number)
        self._validate_seller(seller, SHEET_12, row_number)
        hsn = text(first_value(row, ["hsn number"])) or ""
        summary = result.debug.setdefault("hsn_summary", {})
        item = summary.setdefault(
            hsn,
            {
                "gstin": seller,
                "hsn": hsn,
                "qty": Decimal("0.00"),
                "total_value": Decimal("0.00"),
                "taxable_value": Decimal("0.00"),
                "igst": Decimal("0.00"),
                "cgst": Decimal("0.00"),
                "sgst": Decimal("0.00"),
                "cess": Decimal("0.00"),
            },
        )
        for key, names in {
            "qty": ["total quantity"],
            "total_value": ["total value"],
            "taxable_value": ["total taxable value"],
            "igst": ["igst amount"],
            "cgst": ["cgst amount"],
            "sgst": ["sgst amount"],
            "cess": ["cess amount"],
        }.items():
            item[key] += _decimal(first_value(row, names), names[0], row_number)

    def _parse_gstr8(
        self, row: dict[str, Any], row_number: int, result: ParseResult
    ) -> None:
        seller = _gstin(row, ["gstin of seller"], SHEET_GSTR8, row_number)
        self._validate_seller(seller, SHEET_GSTR8, row_number)
        etin = _gstin(row, ["tcs gstin of snapdeal"], SHEET_GSTR8, row_number)
        summary = result.debug.setdefault("gstr8_summary", [])
        summary.append(
            {
                "seller_gstin": seller,
                "seller_code": text(first_value(row, ["seller code"])),
                "etin": etin,
                "gross_taxable_value": _decimal(
                    first_value(row, ["gross taxable value"]),
                    "gross taxable value",
                    row_number,
                ),
                "taxable_sales_return_value": _decimal(
                    first_value(row, ["taxable sales return value"]),
                    "taxable sales return value",
                    row_number,
                ),
                "net_taxable_value": _decimal(
                    first_value(row, ["net taxable value"]),
                    "net taxable value",
                    row_number,
                ),
                "tcs_rate": _rate(first_value(row, ["tcs %"]), "tcs %", row_number),
                "tcs_igst": _decimal(
                    first_value(row, ["tcs igst amount"]),
                    "tcs igst amount",
                    row_number,
                ),
                "tcs_cgst": _decimal(
                    first_value(row, ["tcs cgst amount"]),
                    "tcs cgst amount",
                    row_number,
                ),
                "tcs_sgst": _decimal(
                    first_value(row, ["tcs sgst amount"]),
                    "tcs sgst amount",
                    row_number,
                ),
                "igst": _decimal(
                    first_value(row, ["igst amount"]), "igst amount", row_number
                ),
                "cgst": _decimal(
                    first_value(row, ["cgst amount"]), "cgst amount", row_number
                ),
                "sgst": _decimal(
                    first_value(row, ["sgst amount"]), "sgst amount", row_number
                ),
            }
        )

    def _parse_series(
        self, row: dict[str, Any], row_number: int, result: ParseResult
    ) -> None:
        gstin = _gstin(row, ["gstin"], SHEET_SERIES, row_number)
        self._validate_seller(gstin, SHEET_SERIES, row_number)
        result.debug.setdefault("invoice_series", []).append(
            {
                "trx_type": text(first_value(row, ["trx type"])),
                "gstin": gstin,
                "from": text(first_value(row, ["invoice series from"])),
                "to": text(first_value(row, ["invoice series to"])),
                "total": _decimal(
                    first_value(row, ["total number of invoices"]),
                    "total number of invoices",
                    row_number,
                ),
                "cancelled": _decimal(
                    first_value(row, ["cancelled if any"]),
                    "cancelled if any",
                    row_number,
                ),
                "net": _decimal(
                    first_value(row, ["net invoice issued"]),
                    "net invoice issued",
                    row_number,
                ),
            }
        )

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult(debug=new_pos_debug(self.platform))
        seen_keys: set[tuple[Any, ...]] = set()
        for path in files:
            try:
                sheets = {name: frame for name, frame in raw_frames(path)}
                missing = sorted(
                    (set(REQUIRED_HEADERS) | {SHEET_GSTR8}) - set(sheets)
                )
                if missing:
                    raise ValueError(
                        f"Unsupported Snapdeal GST report format: missing sheet(s) {', '.join(missing)}"
                    )
                result.debug.setdefault("ignored_sheets", []).append(SHEET_GSTR8)
                for sheet in (
                    SHEET_5B,
                    SHEET_7A,
                    SHEET_7B,
                    SHEET_12,
                    SHEET_GSTR8,
                    SHEET_SERIES,
                ):
                    headers, data = _headers(sheets[sheet])
                    if sheet == SHEET_GSTR8:
                        _require_header_set(sheet, headers, GSTR8_HEADERS)
                    else:
                        _require_headers(sheet, headers)
                    for index, series in data.iterrows():
                        # The Snapdeal export always places headers in row 1.
                        # Keep the Excel row number in errors/debug even when
                        # pandas has retained blank rows in the frame.
                        row_number = int(index) + 2
                        row = series.to_dict()
                        if sheet == SHEET_5B:
                            txn = self._parse_5b(row, row_number, path.name)
                            self._validate_tax_amount(
                                result,
                                sheet=sheet,
                                row_number=row_number,
                                taxable=txn["taxable_value"],
                                rate=txn["gst_rate"],
                                actual=txn["igst"],
                                field="igst amount",
                            )
                            finalized = finalize_transaction(txn)
                        elif sheet == SHEET_7A:
                            self._record_aggregate_source(
                                result, sheet, row, row_number
                            )
                            finalized = finalize_transaction(
                                self._parse_aggregate(
                                    row, row_number, sheet, True, path.name
                                )
                            )
                        elif sheet == SHEET_7B:
                            self._record_aggregate_source(
                                result, sheet, row, row_number
                            )
                            finalized = finalize_transaction(
                                self._parse_aggregate(
                                    row, row_number, sheet, False, path.name
                                )
                            )
                        elif sheet == SHEET_12:
                            self._parse_hsn(row, row_number, result)
                            continue
                        elif sheet == SHEET_GSTR8:
                            self._parse_gstr8(row, row_number, result)
                            continue
                        else:
                            self._parse_series(row, row_number, result)
                            continue
                        key = self._source_key(sheet, finalized)
                        if key in seen_keys:
                            result.debug.setdefault("duplicate_rows", []).append(
                                {"file": path.name, "sheet": sheet, "row": row_number}
                            )
                            continue
                        seen_keys.add(key)
                        self._record_source_totals(result, sheet, finalized)
                        result.transactions.append(finalized)
                        if sheet in (SHEET_5B, SHEET_7A, SHEET_7B):
                            txn = result.transactions[-1]
                            observe_pos_debug(
                                result.debug,
                                row_number,
                                resolve_pos(row, txn, self.platform),
                                row,
                            )
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        hsn_summary = result.debug.get("hsn_summary")
        if isinstance(hsn_summary, dict):
            result.debug["hsn_summary"] = list(hsn_summary.values())
        return result
