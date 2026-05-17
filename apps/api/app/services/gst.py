from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json

from app.services.validation import money


def classify_supply(seller_gstin: str, pos: str | None) -> str:
    seller_state = seller_gstin[:2]
    return "INTRA" if pos and seller_state == pos else "INTER"


def normalize_tax_split(txn: dict) -> dict:
    txn = dict(txn)
    sply_ty = classify_supply(str(txn.get("gstin", "")), txn.get("buyer_state_code"))
    taxable = money(txn.get("taxable_value"))
    rate = money(txn.get("gst_rate"))
    total_tax = money(txn.get("igst")) + money(txn.get("cgst")) + money(txn.get("sgst"))
    if total_tax == Decimal("0.00") and rate:
        total_tax = money(taxable * rate / Decimal("100"))
    if sply_ty == "INTER":
        txn["igst"] = total_tax
        txn["cgst"] = Decimal("0.00")
        txn["sgst"] = Decimal("0.00")
    else:
        half = money(total_tax / Decimal("2"))
        txn["igst"] = Decimal("0.00")
        txn["cgst"] = half
        txn["sgst"] = money(total_tax - half)
    return txn


def build_gstr1_json(gstin: str, period: str, rows: list[dict]) -> dict:
    b2cs = defaultdict(lambda: {"txval": Decimal("0"), "iamt": Decimal("0"), "camt": Decimal("0"), "samt": Decimal("0"), "csamt": Decimal("0")})
    supeco = defaultdict(lambda: {"suppval": Decimal("0"), "igst": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0"), "cess": Decimal("0")})
    docs = defaultdict(list)

    for row in rows:
        normalized = normalize_tax_split(row)
        sply_ty = classify_supply(gstin, normalized.get("buyer_state_code"))
        key = (sply_ty, str(money(normalized.get("gst_rate")).normalize()), normalized.get("buyer_state_code") or "97", "OE")
        b2cs[key]["txval"] += money(normalized.get("taxable_value"))
        b2cs[key]["iamt"] += money(normalized.get("igst"))
        b2cs[key]["camt"] += money(normalized.get("cgst"))
        b2cs[key]["samt"] += money(normalized.get("sgst"))
        b2cs[key]["csamt"] += money(normalized.get("cess"))
        etin = normalized.get("etin") or "UNKNOWN"
        supeco[etin]["suppval"] += money(normalized.get("taxable_value"))
        supeco[etin]["igst"] += money(normalized.get("igst"))
        supeco[etin]["cgst"] += money(normalized.get("cgst"))
        supeco[etin]["sgst"] += money(normalized.get("sgst"))
        supeco[etin]["cess"] += money(normalized.get("cess"))
        doc_type = str(normalized.get("doc_type") or "invoice").lower()
        doc_num = 5 if "credit" in doc_type else 4 if "debit" in doc_type else 1
        if normalized.get("invoice_no"):
            docs[doc_num].append(str(normalized["invoice_no"]))

    b2cs_list = []
    for (sply_ty, rate, pos, typ), amounts in sorted(b2cs.items()):
        b2cs_list.append({
            "sply_ty": sply_ty,
            "rt": float(Decimal(rate)),
            "typ": typ,
            "pos": pos,
            "txval": float(money(amounts["txval"])),
            "iamt": float(money(amounts["iamt"])),
            "camt": float(money(amounts["camt"])),
            "samt": float(money(amounts["samt"])),
            "csamt": float(money(amounts["csamt"])),
        })

    supeco_list = []
    for etin, amounts in sorted(supeco.items()):
        supeco_list.append({
            "etin": etin,
            "suppval": float(money(amounts["suppval"])),
            "igst": float(money(amounts["igst"])),
            "cgst": float(money(amounts["cgst"])),
            "sgst": float(money(amounts["sgst"])),
            "cess": float(money(amounts["cess"])),
            "flag": "N",
        })

    doc_det = []
    for doc_num, invoice_numbers in sorted(docs.items()):
        unique_docs = sorted(set(invoice_numbers))
        if not unique_docs:
            continue
        doc_det.append({
            "doc_num": doc_num,
            "docs": [{
                "num": 1,
                "from": unique_docs[0],
                "to": unique_docs[-1],
                "totnum": len(unique_docs),
                "cancel": 0,
                "net_issue": len(unique_docs),
            }],
        })

    payload = {
        "gstin": gstin,
        "fp": period,
        "version": "GST3.1.6",
        "hash": "hash",
        "b2cs": b2cs_list,
        "supeco": {"supeco_det": supeco_list},
        "doc_issue": {"doc_det": doc_det},
    }
    payload["hash"] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload

