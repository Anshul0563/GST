import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.validation import money
from app.utils.states import STATE_CODES


EXCEL_FORMULA_PREFIXES = ("=", "+", "-", "@")
SHEET_ORDER = ["b2b,sez,de", "b2cl", "b2cs", "cdnr", "hsn", "hsn(b2b)", "hsn(b2c)", "exemp", "eco", "docs"]
ETIN_NAMES = {
    "07AARCM9332R1CQ": "meesho",
    "07AACCF0683K1CU": "flipkart",
    "07AAICA3918J1CV": "amazon",
}
STATE_LABELS = {
    "26": "Dadra & Nagar Haveli & Daman & Diu",
    "35": "Andaman & Nicobar Islands",
}


def safe_excel_value(value):
    if isinstance(value, str) and value.startswith(EXCEL_FORMULA_PREFIXES):
        return "'" + value
    return value


def _amount(value: Any) -> float:
    return float(money(value))


def _state_label(code: object) -> str:
    state_code = str(code or "").zfill(2)
    name = STATE_LABELS.get(state_code) or STATE_CODES.get(state_code) or ""
    return f"{state_code}-{name}" if name else state_code


def _operator_name(etin: str) -> str:
    return ETIN_NAMES.get(etin, etin)


def _sheet(rows: list[list[Any]]) -> pd.DataFrame:
    return pd.DataFrame([[safe_excel_value(value) for value in row] for row in rows])


def _write_sheet(writer: pd.ExcelWriter, name: str, rows: list[list[Any]]) -> None:
    _sheet(rows).to_excel(writer, sheet_name=name, index=False, header=False)


def _b2b_rows() -> list[list[Any]]:
    return [
        ["Summary For B2B, SEZ, DE (4A, 4B, 6B, 6C)", None, None, None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of Recipients", None, "No. of Invoices", None, "Total Invoice Value", None, None, None, None, None, None, "Total Taxable Value", "Total Cess"],
        [0, None, 0, None, 0, None, None, None, None, None, None, 0, 0],
        ["GSTIN/UIN of Recipient", "Receiver Name", "Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply", "Reverse Charge", "Applicable % of Tax Rate", "Invoice Type", "E-Commerce GSTIN", "Rate", "Taxable Value", "Cess Amount"],
    ]


def _b2cl_rows() -> list[list[Any]]:
    return [
        ["Summary For B2CL(5)", None, None, None, None, None, None, None, "HELP"],
        ["No. of Invoices", None, None, None, None, None, None, None, None],
        [0, None, 0, None, None, None, 0, None, None],
        ["Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"],
    ]


def _b2cs_rows(payload: dict) -> list[list[Any]]:
    records = payload.get("b2cs", [])
    total_taxable = sum(money(item.get("txval")) for item in records)
    total_cess = sum(money(item.get("csamt")) for item in records)
    rows = [
        ["Summary For B2CS(7)", None, None, None, None, None, "HELP"],
        [None, None, None, None, "Total Taxable  Value", "Total Cess", None],
        [None, None, None, None, _amount(total_taxable), _amount(total_cess), None],
        ["Type", "Place Of Supply", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"],
    ]
    for item in records:
        rows.append([
            item.get("typ", "OE"),
            _state_label(item.get("pos")),
            None,
            item.get("rt"),
            _amount(item.get("txval")),
            _amount(item.get("csamt")),
            None,
        ])
    return rows


def _cdnr_rows() -> list[list[Any]]:
    return [
        ["Summary For CDNR(9B)", None, None, None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of Recipients", None, "No. of Notes", None, None, None, None, None, "Total Note Value", None, None, "Total Taxable Value", "Total Cess"],
        [0, None, 0, None, None, None, None, None, 0, None, None, 0, 0],
        ["GSTIN/UIN of Recipient", "Receiver Name", "Note Number", "Note Date", "Note Type", "Place Of Supply", "Reverse Charge", "Note Supply Type", "Note Value", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount"],
    ]


def _hsn_rows() -> list[list[Any]]:
    return [
        ["Summary For HSN(12)", None, None, None, None, None, None, None, None, None, "HELP"],
        ["No. of HSN", None, None, None, "Total Value", None, "Total Taxable Value", "Total Integrated Tax", "Total Central Tax", "Total State/UT Tax", "Total Cess"],
        [0, None, None, None, 0, None, 0, 0, 0, 0, 0],
        ["HSN", "Description", "UQC", "Total Quantity", "Total Value", "Rate", "Taxable Value", "Integrated Tax Amount", "Central Tax Amount", "State/UT Tax Amount", "Cess Amount"],
    ]


def _exemp_rows() -> list[list[Any]]:
    return [
        ["Summary For Nil rated, exempted and non GST outward supplies (8)", None, None, "HELP"],
        [None, "Total Nil Rated Supplies", "Total Exempted Supplies", "Total Non-GST Supplies"],
        [None, 0, 0, 0],
        ["Description", "Nil Rated Supplies", "Exempted(other than nil rated/non GST supply)", "Non-GST Supplies"],
        ["Inter-State supplies to registered persons", None, None, None],
        ["Intra-State supplies to registered persons", None, None, None],
        ["Inter-State supplies to unregistered persons", None, None, None],
        ["Intra-State supplies to unregistered persons", None, None, None],
    ]


def _eco_rows(payload: dict) -> list[list[Any]]:
    records = payload.get("supeco", {}).get("clttx", payload.get("supeco", {}).get("supeco_det", []))
    rows = [
        ["Summary For Supplies through ECO-14", None, None, None, None, None, None, "HELP"],
        [None, "No. of E-Commerce Operator", None, "Total Net Value of Supplies", "Total Integrated Tax", "Total Central Tax", "Total State/UT Tax", "Total Cess"],
        [None, len(records), None, _amount(sum(money(item.get("suppval")) for item in records)), _amount(sum(money(item.get("igst")) for item in records)), _amount(sum(money(item.get("cgst")) for item in records)), _amount(sum(money(item.get("sgst")) for item in records)), _amount(sum(money(item.get("cess")) for item in records))],
        ["Nature of Supply", "GSTIN of E-Commerce Operator", "E-Commerce Operator Name", "Net value of supplies", "Integrated tax", "Central tax", "State/UT tax", "Cess"],
    ]
    for item in records:
        etin = str(item.get("etin") or "")
        rows.append([
            "Liable to collect tax u/s 52(TCS)",
            etin,
            _operator_name(etin),
            _amount(item.get("suppval")),
            _amount(item.get("igst")),
            _amount(item.get("cgst")),
            _amount(item.get("sgst")),
            _amount(item.get("cess")),
        ])
    return rows


def _docs_rows(payload: dict) -> list[list[Any]]:
    docs = [
        (section.get("doc_typ"), doc)
        for section in payload.get("doc_issue", {}).get("doc_det", [])
        for doc in section.get("docs", [])
    ]
    rows = [
        ["Summary of documents issued during the tax period (13)", None, None, None, "HELP"],
        [None, None, None, "Total Number", "Total Cancelled"],
        [None, None, None, sum(int(doc.get("totnum") or 0) for _, doc in docs), sum(int(doc.get("cancel") or 0) for _, doc in docs)],
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
    return rows


def write_gstr1_excel(path: Path, payload: dict, rows: list[dict], errors: list[dict] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = {
        "b2b,sez,de": _b2b_rows(),
        "b2cl": _b2cl_rows(),
        "b2cs": _b2cs_rows(payload),
        "cdnr": _cdnr_rows(),
        "hsn": _hsn_rows(),
        "hsn(b2b)": _hsn_rows(),
        "hsn(b2c)": _hsn_rows(),
        "exemp": _exemp_rows(),
        "eco": _eco_rows(payload),
        "docs": _docs_rows(payload),
    }
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for sheet_name in SHEET_ORDER:
            _write_sheet(writer, sheet_name, sheets[sheet_name])
    return path


def write_internal_gstr1_audit_excel(path: Path, payload: dict, rows: list[dict], errors: list[dict] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    b2cs = pd.DataFrame(payload.get("b2cs", []))
    supeco = pd.DataFrame(payload.get("supeco", {}).get("clttx", payload.get("supeco", {}).get("supeco_det", [])))
    doc_rows = []
    for group in payload.get("doc_issue", {}).get("doc_det", []):
        for doc in group.get("docs", []):
            doc_rows.append({"doc_num": group["doc_num"], **doc})
    raw = pd.DataFrame([{key: safe_excel_value(value) for key, value in row.items() if key != "raw_row_json"} for row in rows])
    platform_summary = raw.groupby("platform", dropna=False)[["taxable_value", "igst", "cgst", "sgst"]].sum().reset_index() if not raw.empty else pd.DataFrame()
    state_summary = raw.groupby("buyer_state_code", dropna=False)[["taxable_value", "igst", "cgst", "sgst"]].sum().reset_index() if not raw.empty else pd.DataFrame()

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        pd.DataFrame([{"gstin": payload["gstin"], "period": payload["fp"], "sections": json.dumps({"b2cs": len(b2cs), "supeco": len(supeco)})}]).to_excel(writer, sheet_name="Summary", index=False)
        b2cs.to_excel(writer, sheet_name="B2CS", index=False)
        supeco.to_excel(writer, sheet_name="SUPECO", index=False)
        pd.DataFrame(doc_rows).to_excel(writer, sheet_name="Document Issue", index=False)
        raw.to_excel(writer, sheet_name="Raw Merged Data", index=False)
        pd.DataFrame(errors or []).to_excel(writer, sheet_name="Error Report", index=False)
        platform_summary.to_excel(writer, sheet_name="Platform Summary", index=False)
        state_summary.to_excel(writer, sheet_name="State Summary", index=False)
    return path
