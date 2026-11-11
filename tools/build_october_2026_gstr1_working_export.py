from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import json

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.parsers.factory import get_parser


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reconciliation_reports" / "GSTR1-October-2026-working-export.xlsx"
GSTIN = "07TCRPS8655B1ZK"
PERIOD = "102026"

SOURCES = {
    "meesho": [
        Path("/home/jarvis/Downloads/gst_3412749_10_2026/tcs_sales.xlsx"),
        Path("/home/jarvis/Downloads/gst_3412749_10_2026/tcs_sales_return.xlsx"),
        Path("/home/jarvis/Downloads/3412749_2026-10-01_2026-10-31_TAX_INVOICE/Tax_invoice_details.xlsx"),
    ],
    "flipkart": [
        Path("/home/jarvis/Downloads/044ae62c-b176-4ce6-b8d8-bb62c61044db_1794237021000.xlsx"),
    ],
    "snapdeal": [
        Path("/home/jarvis/Downloads/Sc8f1c_OCT_2026_84216239_446663.xlsx"),
    ],
}


def dec(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def raw_amount(row: dict, key: str) -> Decimal:
    return dec(row.get(key))


def financial(row: dict) -> bool:
    return (
        row.get("validation_status") == "valid"
        and row.get("invoice_no")
        and any(raw_amount(row, field) != 0 for field in ("taxable_value", "igst", "cgst", "sgst", "cess"))
        and row.get("_gstr1_section") is None
    )


def row_status(row: dict) -> str:
    if row.get("platform") == "flipkart" and row.get("doc_type") == "debit_note" and raw_amount(row, "taxable_value") < 0:
        return "HOLD - negative-signed debit note requires source/business confirmation"
    if row.get("platform") == "snapdeal" and row.get("doc_type") in {"credit_note", "debit_note"}:
        return "HOLD - Snapdeal source is aggregate and has no note-level financial row"
    return "INCLUDED - B2C Others candidate"


def state_name(code: object) -> str:
    return "" if code in (None, "") else str(code)


def amount_dict(rows: list[dict]) -> dict[str, Decimal]:
    return {
        field: sum((raw_amount(row, field) for row in rows), Decimal("0.00"))
        for field in ("taxable_value", "igst", "cgst", "sgst", "cess", "gross_amount", "tcs", "tds")
    }


def append_sheet(wb: Workbook, name: str, columns: list[str], rows: list[dict]) -> None:
    ws = wb.create_sheet(name)
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17365D")
    for row in rows:
        ws.append([row.get(column, "") for column in columns])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for index, column in enumerate(columns, 1):
        width = min(48, max(12, len(column) + 2, *(len(str(ws.cell(r, index).value or "")) for r in range(2, min(ws.max_row, 100) + 1))))
        ws.column_dimensions[get_column_letter(index)].width = width


def main() -> None:
    parsed: dict[str, list[dict]] = {}
    for platform, paths in SOURCES.items():
        result = get_parser(platform)(GSTIN, PERIOD).parse(paths)
        if result.errors:
            raise RuntimeError(f"{platform} parser errors: {result.errors}")
        parsed[platform] = result.transactions

    all_financial: list[dict] = []
    for platform, rows in parsed.items():
        for row in rows:
            row = dict(row)
            row["platform"] = platform
            if financial(row):
                all_financial.append(row)

    assert len(all_financial) == 831, len(all_financial)

    b2b = []
    b2c_large = []
    b2c_others = []
    notes = []
    audit = []
    for number, row in enumerate(all_financial, 1):
        recipient = row.get("recipient_gstin")
        gross = raw_amount(row, "gross_amount")
        status = row_status(row)
        common = {
            "audit_row": number,
            "platform": row.get("platform"),
            "invoice_no": row.get("invoice_no"),
            "document_type": row.get("doc_type"),
            "invoice_date": row.get("invoice_date"),
            "document_date": row.get("document_date"),
            "order_id": row.get("order_id"),
            "order_item_id": row.get("order_item_id"),
            "recipient_gstin": recipient or "",
            "pos": state_name(row.get("buyer_state_code")),
            "hsn": row.get("hsn") or "",
            "product_name": row.get("product_name") or "",
            "uqc": row.get("uqc") or "",
            "quantity": row.get("qty") if row.get("qty") not in (None, "") else "",
            "gst_rate": row.get("gst_rate") or "",
            "taxable_value": raw_amount(row, "taxable_value"),
            "igst": raw_amount(row, "igst"),
            "cgst": raw_amount(row, "cgst"),
            "sgst": raw_amount(row, "sgst"),
            "cess": raw_amount(row, "cess"),
            "gross_amount_source_field": gross,
            "filing_status": status,
        }
        audit.append({**common, "source_file": row.get("source_file"), "source_sheet_or_section": row.get("_gstr1_section") or "financial source row"})
        if row.get("doc_type") in {"credit_note", "debit_note"}:
            notes.append(common)
            continue
        if recipient:
            b2b.append(common)
        elif gross > Decimal("250000"):
            b2c_large.append(common)
        else:
            b2c_others.append(common)

    # Add explicit source-level exceptions that do not appear as financial rows.
    exceptions = [
        {"severity": "BLOCKER", "platform": "flipkart", "issue": "LZAA9B7270000022 is classified as a debit note but source taxable and IGST are negative", "impact": "Held from filing candidate until source/business confirmation; included in audit totals."},
        {"severity": "WARNING", "platform": "meesho", "issue": "Source vs normalized reconciliation differs", "impact": "Taxable +₹0.06, GST -₹0.07, invoice value -₹0.01; no forced adjustment."},
        {"severity": "WARNING", "platform": "snapdeal", "issue": "Section 7(B)(2) is aggregate state-level data and does not provide invoice-level value/note IDs", "impact": "B2C Others working rows are included; B2C Large and note-level exports cannot be asserted."},
        {"severity": "WARNING", "platform": "snapdeal", "issue": "Section 12 HSN and Section 3 GSTR-8 summaries are not transaction rows", "impact": "Retained only in HSN/audit context; excluded from financial totals."},
        {"severity": "INFO", "platform": "all", "issue": "No recipient GSTIN was present in included financial rows", "impact": "B2B sheet is empty; records are B2C candidates."},
        {"severity": "INFO", "platform": "all", "issue": "No invoice gross value exceeded ₹250,000", "impact": "B2C Large sheet is empty; records are B2C Others candidates."},
    ]

    # Source HSN summaries are kept separate from transaction rows to prevent double counting.
    hsn = []
    snap_hsn = parsed["snapdeal"]
    for row in snap_hsn:
        if row.get("_gstr1_section") == "hsn":
            hsn.append({
                "platform": "snapdeal",
                "hsn": row.get("hsn") or "",
                "description": row.get("product_name") or "",
                "uqc": row.get("uqc") or "PCS",
                "quantity": row.get("qty") or "",
                "taxable_value": raw_amount(row, "taxable_value"),
                "igst": raw_amount(row, "igst"),
                "cgst": raw_amount(row, "cgst"),
                "sgst": raw_amount(row, "sgst"),
                "cess": raw_amount(row, "cess"),
                "source_note": "Section 12 source summary; excluded from financial audit total",
            })
    hsn_groups = defaultdict(lambda: {field: Decimal("0.00") for field in ("quantity", "taxable_value", "igst", "cgst", "sgst", "cess")})
    for row in all_financial:
        key = (row.get("platform"), row.get("hsn") or "", row.get("product_name") or "", row.get("uqc") or "")
        group = hsn_groups[key]
        group["quantity"] += Decimal(str(row.get("qty") or 0))
        for field in ("taxable_value", "igst", "cgst", "sgst", "cess"):
            group[field] += raw_amount(row, field)
    for (platform, code, description, uqc), values in sorted(hsn_groups.items()):
        hsn.append({"platform": platform, "hsn": code, "description": description, "uqc": uqc, **values, "source_note": "Aggregated from 831 financial rows"})
    hsn.extend([])

    series = [
        {"platform": "meesho", "document_type": "invoice", "source_count": 612, "cancelled": "", "net_count": 612, "basis": "financial sales rows"},
        {"platform": "meesho", "document_type": "credit_note", "source_count": 162, "cancelled": "", "net_count": 162, "basis": "financial return rows"},
        {"platform": "flipkart", "document_type": "invoice", "source_count": 29, "cancelled": "", "net_count": 29, "basis": "Sales Report financial rows"},
        {"platform": "flipkart", "document_type": "credit_note", "source_count": 14, "cancelled": "", "net_count": 14, "basis": "Sales Report + Cash Back Report"},
        {"platform": "flipkart", "document_type": "debit_note", "source_count": 1, "cancelled": "", "net_count": 1, "basis": "held pending sign confirmation"},
        {"platform": "snapdeal", "document_type": "invoice", "source_count": 27, "cancelled": 9, "net_count": 18, "basis": "Invoice Series source metadata"},
        {"platform": "snapdeal", "document_type": "credit_note", "source_count": 11, "cancelled": 0, "net_count": 0, "basis": "Invoice Series source metadata; inconsistent with note-level financial detail unavailable"},
    ]

    platform_rows = []
    for platform in ("meesho", "flipkart", "snapdeal"):
        rows = [r for r in all_financial if r.get("platform") == platform]
        amounts = amount_dict(rows)
        platform_rows.append({"platform": platform, "financial_rows": len(rows), **amounts, "total_gst": amounts["igst"] + amounts["cgst"] + amounts["sgst"] + amounts["cess"]})

    totals = amount_dict(all_financial)
    summary = [
        {"metric": "AUDITED_SOURCE_NORMALIZED_INCLUDING_HELD_ROWS", "value": "", "taxable_value": totals["taxable_value"], "igst": totals["igst"], "cgst": totals["cgst"], "sgst": totals["sgst"], "cess": totals["cess"], "total_gst": totals["igst"] + totals["cgst"] + totals["sgst"] + totals["cess"], "status": "Audit total only; not filing-ready until exceptions resolved"},
        {"metric": "FINANCIAL_ROWS", "value": 831, "status": "13 Snapdeal + 44 Flipkart + 774 Meesho"},
        {"metric": "NET_INVOICE_VALUE", "value": "NOT REPORTED", "status": "Snapdeal invoice value unavailable; do not use gross_amount total ₹70,566.93"},
    ]

    formulas = [
        {"formula": "Net taxable value", "definition": "SUM(row taxable_value), preserving source signs for returns/adjustments"},
        {"formula": "IGST", "definition": "SUM(row igst)"},
        {"formula": "CGST", "definition": "SUM(row cgst)"},
        {"formula": "SGST/UTGST", "definition": "SUM(row sgst)"},
        {"formula": "Total GST", "definition": "IGST + CGST + SGST + Cess"},
        {"formula": "B2C Others", "definition": "No recipient GSTIN and source gross amount <= ₹250,000; grouped by POS and GST rate for portal working"},
        {"formula": "B2C Large", "definition": "No included row met the ₹250,000 interstate invoice-value threshold"},
        {"formula": "B2B", "definition": "No included row had a recipient GSTIN; no rows invented"},
    ]

    wb = Workbook()
    wb.remove(wb.active)
    append_sheet(wb, "README", ["item", "value"], [
        {"item": "Workbook status", "value": "Working export - not filing-ready until Exceptions are resolved"},
        {"item": "GSTIN", "value": GSTIN},
        {"item": "Filing period", "value": "October 2026"},
        {"item": "Financial rows", "value": 831},
        {"item": "Portal JSON", "value": "Not generated: unresolved debit-note sign, aggregate Snapdeal data, and Meesho reconciliation discrepancy"},
    ])
    columns = ["audit_row", "platform", "invoice_no", "document_type", "invoice_date", "document_date", "order_id", "order_item_id", "recipient_gstin", "pos", "hsn", "product_name", "uqc", "quantity", "gst_rate", "taxable_value", "igst", "cgst", "sgst", "cess", "gross_amount_source_field", "filing_status"]
    append_sheet(wb, "B2B", columns, b2b)
    append_sheet(wb, "B2C_Large", columns, b2c_large)
    append_sheet(wb, "B2C_Others", columns, b2c_others)
    append_sheet(wb, "Credit_Debit_Notes", columns, notes)
    append_sheet(wb, "HSN_Summary", ["platform", "hsn", "description", "uqc", "quantity", "taxable_value", "igst", "cgst", "sgst", "cess", "source_note"], hsn)
    append_sheet(wb, "Document_Series", ["platform", "document_type", "source_count", "cancelled", "net_count", "basis"], series)
    append_sheet(wb, "Platform_Reconciliation", ["platform", "financial_rows", "taxable_value", "igst", "cgst", "sgst", "cess", "gross_amount", "tcs", "tds", "total_gst"], platform_rows)
    append_sheet(wb, "Consolidated_Summary", ["metric", "value", "taxable_value", "igst", "cgst", "sgst", "cess", "total_gst", "status"], summary)
    append_sheet(wb, "Formulas", ["formula", "definition"], formulas)
    append_sheet(wb, "Exceptions", ["severity", "platform", "issue", "impact"], exceptions)
    append_sheet(wb, "Audit_Trail", ["audit_row", "platform", "invoice_no", "document_type", "invoice_date", "document_date", "order_id", "order_item_id", "recipient_gstin", "pos", "hsn", "product_name", "uqc", "quantity", "gst_rate", "taxable_value", "igst", "cgst", "sgst", "cess", "gross_amount_source_field", "filing_status", "source_file", "source_sheet_or_section"], audit)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
