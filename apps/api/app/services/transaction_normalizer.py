from decimal import Decimal

import pandas as pd

from app.services.gst import classify_supply
from app.services.gst_rate_resolver import resolve_gst_rate
from app.services.validation import money, round_money, validate_transaction


TAX_FIELDS = ("igst", "cgst", "sgst", "cess", "tcs", "tds")
VALUE_FIELDS = ("taxable_value", "gross_amount", "discount_seller", "discount_platform", "settlement_amount")


def _same_sign(value, sign: Decimal):
    amount = money(value)
    if amount == Decimal("0.00"):
        return amount
    return abs(amount) * sign


def infer_rate(txn: dict) -> Decimal:
    resolution = resolve_gst_rate(txn)
    if resolution.rate is None:
        return money(txn.get("gst_rate"))
    return resolution.rate


def infer_taxable(txn: dict) -> Decimal:
    taxable = money(txn.get("taxable_value"))
    if taxable != Decimal("0.00"):
        return taxable
    gross = money(txn.get("gross_amount"))
    rate = money(txn.get("gst_rate"))
    if gross != Decimal("0.00") and rate > 0:
        return round_money(gross * Decimal("100") / (Decimal("100") + rate))
    return taxable


def apply_doc_sign(txn: dict) -> dict:
    if txn.get("_preserve_source_sign"):
        txn["taxable_value"] = infer_taxable(txn)
        for field in TAX_FIELDS + VALUE_FIELDS:
            if field == "taxable_value":
                continue
            txn[field] = money(txn.get(field))
        txn["qty"] = money(txn.get("qty"))
        return txn
    doc_type = str(txn.get("doc_type") or "invoice").lower()
    sign = Decimal("-1") if "credit" in doc_type or "refund" in doc_type or "return" in doc_type else Decimal("1")
    txn["taxable_value"] = _same_sign(infer_taxable(txn), sign)
    for field in TAX_FIELDS + VALUE_FIELDS:
        if field == "taxable_value":
            continue
        txn[field] = _same_sign(txn.get(field), sign)
    if money(txn.get("qty")) != Decimal("0.00"):
        txn["qty"] = _same_sign(txn.get("qty"), sign)
    return txn


def normalize_tax_split(txn: dict) -> dict:
    txn = dict(txn)
    txn["gst_rate"] = infer_rate(txn)
    txn = apply_doc_sign(txn)
    if txn.get("_preserve_source_tax_split"):
        txn["igst"] = money(txn.get("igst"))
        txn["cgst"] = money(txn.get("cgst"))
        txn["sgst"] = money(txn.get("sgst"))
        txn["cess"] = money(txn.get("cess"))
        return txn
    supply_type = classify_supply(str(txn.get("gstin", "")), txn.get("buyer_state_code"))
    taxable = money(txn.get("taxable_value"))
    rate = money(txn.get("gst_rate"))
    existing_tax = money(txn.get("igst")) + money(txn.get("cgst")) + money(txn.get("sgst"))
    expected_tax = round_money(taxable * rate / Decimal("100"))
    total_tax = existing_tax if existing_tax != Decimal("0.00") else expected_tax
    if total_tax != Decimal("0.00") and taxable != Decimal("0.00") and (total_tax > 0) != (taxable > 0):
        total_tax = abs(total_tax) * (Decimal("-1") if taxable < 0 else Decimal("1"))
    if supply_type == "INTER":
        txn["igst"] = total_tax
        txn["cgst"] = Decimal("0.00")
        txn["sgst"] = Decimal("0.00")
    else:
        half = round_money(total_tax / Decimal("2"))
        txn["igst"] = Decimal("0.00")
        txn["cgst"] = half
        txn["sgst"] = round_money(total_tax - half)
    txn["cess"] = money(txn.get("cess"))
    return txn


def finalize_transaction(txn: dict) -> dict:
    preserve_source_sign = bool(txn.pop("_preserve_source_sign", False))
    preserve_source_tax_split = bool(txn.pop("_preserve_source_tax_split", False))
    txn["doc_type"] = str(txn.get("doc_type") or "invoice").lower()
    if preserve_source_sign:
        txn["_preserve_source_sign"] = True
    if preserve_source_tax_split:
        txn["_preserve_source_tax_split"] = True
    txn = normalize_tax_split(txn)
    txn.pop("_preserve_source_sign", None)
    txn.pop("_preserve_source_tax_split", None)
    if isinstance(txn.get("invoice_date"), str):
        text_value = txn["invoice_date"].strip()
        dayfirst = not text_value[:4].isdigit()
        parsed = pd.to_datetime(text_value, errors="coerce", dayfirst=dayfirst)
        txn["invoice_date"] = None if pd.isna(parsed) else parsed.date()
    errors = validate_transaction(txn)
    zero_only = errors and all(error in {"Zero amount row", "Zero rate and zero taxable row"} for error in errors)
    txn["validation_status"] = "skipped" if zero_only else "invalid" if errors else "valid"
    txn["validation_errors"] = "; ".join(errors) if errors else None
    return txn
