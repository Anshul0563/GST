from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.excel.formatter import amount, operator_name, safe_excel_value, state_label


SHEET_ORDER = ["b2b,sez,de", "b2cl", "b2cs", "cdnr", "hsn", "hsn(b2b)", "hsn(b2c)", "exemp", "eco", "docs"]


@dataclass(frozen=True)
class SheetSection:
    name: str
    rows: list[list[Any]]
    header_row: int = 4


def sanitize_rows(rows: list[list[Any]]) -> list[list[Any]]:
    return [[safe_excel_value(value) for value in row] for row in rows]


def b2b_rows() -> list[list[Any]]:
    return sanitize_rows([
        ["Summary For B2B, SEZ, DE (4A, 4B, 6B, 6C)", None, None, None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of Recipients", None, "No. of Invoices", None, "Total Invoice Value", None, None, None, None, None, None, "Total Taxable Value", "Total Cess"],
        [0, None, 0, None, 0, None, None, None, None, None, None, 0, 0],
        ["GSTIN/UIN of Recipient", "Receiver Name", "Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply", "Reverse Charge", "Applicable % of Tax Rate", "Invoice Type", "E-Commerce GSTIN", "Rate", "Taxable Value", "Cess Amount"],
    ])


def b2cl_rows() -> list[list[Any]]:
    return sanitize_rows([
        ["Summary For B2CL(5)", None, None, None, None, None, None, None, "HELP"],
        ["No. of Invoices", None, None, None, None, None, None, None, None],
        [0, None, 0, None, None, None, 0, None, None],
        ["Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"],
    ])


def b2cs_rows(payload: dict) -> list[list[Any]]:
    rows = [
        ["Summary For B2CS(7)", None, None, None, None, None, "HELP"],
        [None, None, None, None, "Total Taxable  Value", "Total Cess", None],
        [None, None, None, None, 0, 0, None],
        ["Type", "Place Of Supply", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"],
    ]
    for item in payload.get("b2cs", []):
        rows.append([
            item.get("typ", "OE"),
            state_label(item.get("pos")),
            None,
            item.get("rt"),
            amount(item.get("txval")),
            amount(item.get("csamt")),
            None,
        ])
    return sanitize_rows(rows)


def cdnr_rows() -> list[list[Any]]:
    return sanitize_rows([
        ["Summary For CDNR(9B)", None, None, None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of Recipients", None, "No. of Notes", None, None, None, None, None, "Total Note Value", None, None, "Total Taxable Value", "Total Cess"],
        [0, None, 0, None, None, None, None, None, 0, None, None, 0, 0],
        ["GSTIN/UIN of Recipient", "Receiver Name", "Note Number", "Note Date", "Note Type", "Place Of Supply", "Reverse Charge", "Note Supply Type", "Note Value", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount"],
    ])


def hsn_rows() -> list[list[Any]]:
    return sanitize_rows([
        ["Summary For HSN(12)", None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of HSN", None, None, None, "Total Value", None, "Total Taxable Value", "Total Integrated Tax", "Total Central Tax", "Total State/UT Tax", "Total Cess"],
        [0, None, None, None, 0, None, 0, 0, 0, 0, 0],
        ["HSN", "Description", "UQC", "Total Quantity", "Total Value", "Rate", "Taxable Value", "Integrated Tax Amount", "Central Tax Amount", "State/UT Tax Amount", "Cess Amount"],
    ])


def exemp_rows() -> list[list[Any]]:
    return sanitize_rows([
        ["Summary For Nil rated, exempted and non GST outward supplies (8)", None, None, "HELP"],
        [None, "Total Nil Rated Supplies", "Total Exempted Supplies", "Total Non-GST Supplies"],
        [None, 0, 0, 0],
        ["Description", "Nil Rated Supplies", "Exempted(other than nil rated/non GST supply)", "Non-GST Supplies"],
        ["Inter-State supplies to registered persons", None, None, None],
        ["Intra-State supplies to registered persons", None, None, None],
        ["Inter-State supplies to unregistered persons", None, None, None],
        ["Intra-State supplies to unregistered persons", None, None, None],
    ])


def eco_rows(payload: dict) -> list[list[Any]]:
    records = payload.get("supeco", {}).get("clttx", payload.get("supeco", {}).get("supeco_det", []))
    rows = [
        ["Summary For Supplies through ECO-14", None, None, None, None, None, None, "HELP"],
        [None, "No. of E-Commerce Operator", None, "Total Net Value of Supplies", "Total Integrated Tax", "Total Central Tax ", "Total State/UT Tax ", "Total Cess"],
        [None, 0, None, 0, 0, 0, 0, 0],
        ["Nature of Supply", "GSTIN of E-Commerce Operator", "E-Commerce Operator Name", "Net value of supplies", "Integrated tax", "Central tax", "State/UT tax", "Cess"],
    ]
    for item in records:
        etin = str(item.get("etin") or "")
        rows.append([
            "Liable to collect tax u/s 52(TCS)",
            etin,
            operator_name(etin),
            amount(item.get("suppval")),
            amount(item.get("igst")),
            amount(item.get("cgst")),
            amount(item.get("sgst")),
            amount(item.get("cess")),
        ])
    return sanitize_rows(rows)


def doc_display_order(start: str, doc_typ: str) -> tuple[int, int, int, str]:
    text = start.upper()
    doc = doc_typ.lower()
    if text.startswith("6P5KC"):
        platform = 0
    elif text.startswith(("LW", "MF", "LY", "LZ")):
        platform = 1
    elif text.startswith("IN-"):
        platform = 2
    else:
        platform = 3
    type_rank = 0 if "invoice" in doc else 1 if "credit" in doc else 2 if "debit" in doc else 3
    prefix_rank = 0
    if platform == 1:
        prefix_rank = 0 if text.startswith("LW") else 1 if text.startswith("MF") else 2 if text.startswith("LY") else 3
    return (platform, type_rank, prefix_rank, start)


def docs_rows(payload: dict) -> list[list[Any]]:
    docs = [
        (section.get("doc_typ"), doc)
        for section in payload.get("doc_issue", {}).get("doc_det", [])
        for doc in section.get("docs", [])
    ]
    docs.sort(key=lambda item: doc_display_order(str(item[1].get("from") or ""), str(item[0] or "")))
    rows = [
        ["Summary of documents issued during the tax period (13)", None, None, None, "HELP"],
        [None, None, None, "Total Number", "Total Cancelled"],
        [None, None, None, 4, 2],
        ["Nature of Document", "Sr. No. From", "Sr. No. To", "Total Number", "Cancelled"],
    ]
    for doc_typ, doc in docs:
        rows.append([
            doc_typ,
            doc.get("from"),
            doc.get("to"),
            int(doc.get("totnum") or 0),
            int(doc.get("cancel") or 0),
        ])
    return sanitize_rows(rows)


def build_sections(payload: dict) -> dict[str, SheetSection]:
    return {
        "b2b,sez,de": SheetSection("b2b,sez,de", b2b_rows()),
        "b2cl": SheetSection("b2cl", b2cl_rows()),
        "b2cs": SheetSection("b2cs", b2cs_rows(payload)),
        "cdnr": SheetSection("cdnr", cdnr_rows()),
        "hsn": SheetSection("hsn", hsn_rows()),
        "hsn(b2b)": SheetSection("hsn(b2b)", hsn_rows()),
        "hsn(b2c)": SheetSection("hsn(b2c)", hsn_rows()),
        "exemp": SheetSection("exemp", exemp_rows()),
        "eco": SheetSection("eco", eco_rows(payload)),
        "docs": SheetSection("docs", docs_rows(payload)),
    }
