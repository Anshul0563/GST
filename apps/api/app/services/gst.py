from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import re
from typing import Any

from app.services.validation import money


GST_VERSION = "GST3.1.6"
DOC_NUM = {"invoice": 1, "debit_note": 4, "credit_note": 5}
DOC_TYP = {
    "invoice": "Invoices for outward supply",
    "debit_note": "Debit Note",
    "credit_note": "Credit Note",
}


def classify_supply(seller_gstin: str, pos: str | None) -> str:
    seller_state = seller_gstin[:2]
    return "INTRA" if pos and seller_state == pos else "INTER"


def json_amount(value: Any) -> float:
    return float(money(value))


def valid_for_gstr(row: dict[str, Any]) -> bool:
    if row.get("validation_status") != "valid":
        return False
    if not row.get("buyer_state_code") or not row.get("invoice_no") or not row.get("etin"):
        return False
    rate = money(row.get("gst_rate"))
    taxable = money(row.get("taxable_value"))
    total_tax = money(row.get("igst")) + money(row.get("cgst")) + money(row.get("sgst")) + money(row.get("cess"))
    if rate == Decimal("0.00") or (taxable == Decimal("0.00") and total_tax == Decimal("0.00")):
        return False
    return True


def document_series_key(invoice_no: str) -> str:
    text = str(invoice_no or "").strip()
    if not text:
        return ""
    prefix = re.match(r"^[A-Za-z]+", text)
    if prefix:
        return prefix.group(0).upper()
    alnum_prefix = re.match(r"^[A-Za-z0-9]+?(?=[-_/])", text)
    if alnum_prefix:
        return alnum_prefix.group(0).upper()
    if len(text) >= 5:
        return text[:5].upper()
    return text.upper()


def document_sort_key(invoice_no: str) -> tuple[str, int, str]:
    text = str(invoice_no)
    match = re.search(r"(\d+)(?!.*\d)", text)
    number = int(match.group(1)) if match else -1
    return (document_series_key(text), number, text)


def build_b2cs(gstin: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, Decimal, str, str], dict[str, Decimal]] = defaultdict(lambda: {
        "txval": Decimal("0.00"),
        "iamt": Decimal("0.00"),
        "camt": Decimal("0.00"),
        "samt": Decimal("0.00"),
        "csamt": Decimal("0.00"),
    })
    for row in rows:
        if not valid_for_gstr(row):
            continue
        sply_ty = classify_supply(gstin, row.get("buyer_state_code"))
        key = (sply_ty, money(row.get("gst_rate")), str(row.get("buyer_state_code")), "OE")
        groups[key]["txval"] += money(row.get("taxable_value"))
        groups[key]["iamt"] += money(row.get("igst"))
        groups[key]["camt"] += money(row.get("cgst"))
        groups[key]["samt"] += money(row.get("sgst"))
        groups[key]["csamt"] += money(row.get("cess"))

    output: list[dict[str, Any]] = []
    for (sply_ty, rate, pos, typ), amounts in sorted(groups.items(), key=lambda item: (item[0][0], item[0][2], item[0][1])):
        total_tax = amounts["iamt"] + amounts["camt"] + amounts["samt"] + amounts["csamt"]
        if amounts["txval"] == Decimal("0.00") and total_tax == Decimal("0.00"):
            continue
        if rate == Decimal("0.00"):
            continue
        base = {
            "sply_ty": sply_ty,
            "rt": int(rate) if rate == rate.to_integral_value() else float(rate),
            "typ": typ,
            "pos": pos,
            "txval": json_amount(amounts["txval"]),
        }
        if sply_ty == "INTER":
            base["iamt"] = json_amount(amounts["iamt"])
            base["csamt"] = json_amount(amounts["csamt"])
        else:
            base["camt"] = json_amount(amounts["camt"])
            base["samt"] = json_amount(amounts["samt"])
            base["csamt"] = json_amount(amounts["csamt"])
        output.append(base)
    return output


def build_supeco(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Decimal]] = defaultdict(lambda: {
        "suppval": Decimal("0.00"),
        "igst": Decimal("0.00"),
        "cgst": Decimal("0.00"),
        "sgst": Decimal("0.00"),
        "cess": Decimal("0.00"),
    })
    for row in rows:
        if not valid_for_gstr(row):
            continue
        etin = str(row.get("etin"))
        groups[etin]["suppval"] += money(row.get("taxable_value"))
        groups[etin]["igst"] += money(row.get("igst"))
        groups[etin]["cgst"] += money(row.get("cgst"))
        groups[etin]["sgst"] += money(row.get("sgst"))
        groups[etin]["cess"] += money(row.get("cess"))
    return [{
        "etin": etin,
        "suppval": json_amount(amounts["suppval"]),
        "igst": json_amount(amounts["igst"]),
        "cgst": json_amount(amounts["cgst"]),
        "sgst": json_amount(amounts["sgst"]),
        "cess": json_amount(amounts["cess"]),
        "flag": "N",
    } for etin, amounts in sorted(groups.items())]


def build_doc_issue(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        if not valid_for_gstr(row):
            continue
        doc_type = str(row.get("doc_type") or "invoice").lower()
        if doc_type not in DOC_NUM:
            continue
        invoice_no = str(row.get("invoice_no") or "").strip()
        if not invoice_no:
            continue
        platform = str(row.get("platform") or "unknown").lower()
        grouped[(doc_type, platform, document_series_key(invoice_no))].add(invoice_no)

    doc_det: list[dict[str, Any]] = []
    for doc_type in ("invoice", "credit_note", "debit_note"):
        series = [(key, sorted(values, key=document_sort_key)) for key, values in grouped.items() if key[0] == doc_type]
        if not series:
            continue
        docs = []
        for index, (_key, values) in enumerate(sorted(series, key=lambda item: document_sort_key(item[1][0])), start=1):
            docs.append({
                "num": index,
                "from": values[0],
                "to": values[-1],
                "totnum": len(values),
                "cancel": 0,
                "net_issue": len(values),
            })
        doc_det.append({"doc_num": DOC_NUM[doc_type], "doc_typ": DOC_TYP[doc_type], "docs": docs})
    doc_det.sort(key=lambda item: [1, 5, 4].index(item["doc_num"]))
    return {"doc_det": doc_det}


def build_gstr1_json(gstin: str, period: str, rows: list[dict]) -> dict:
    valid_rows = [row for row in rows if valid_for_gstr(row)]
    return {
        "gstin": gstin,
        "fp": period,
        "version": GST_VERSION,
        "hash": "hash",
        "b2cs": build_b2cs(gstin, valid_rows),
        "supeco": {"clttx": build_supeco(valid_rows)},
        "doc_issue": build_doc_issue(valid_rows),
    }
