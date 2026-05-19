from decimal import Decimal

import pandas as pd

from app.services.gst import classify_supply
from app.services.validation import SUPPORTED_RATES, money, round_money, validate_transaction


TAX_FIELDS = ("igst", "cgst", "sgst", "cess", "tcs", "tds")
VALUE_FIELDS = ("taxable_value", "gross_amount", "discount_seller", "discount_platform", "settlement_amount")


def _same_sign(value, sign: Decimal):
    amount = money(value)
    if amount == Decimal("0.00"):
        return amount
    return abs(amount) * sign


def infer_rate(txn: dict) -> Decimal:
    rate = money(txn.get("gst_rate"))
    if Decimal("0.00") < rate < Decimal("1.00"):
        return nearest_supported_rate(round_money(rate * Decimal("100")))
    taxable = abs(money(txn.get("taxable_value")))
    tax = abs(money(txn.get("igst")) + money(txn.get("cgst")) + money(txn.get("sgst")) + money(txn.get("cess")))
    if rate == Decimal("0.00") and taxable > 0 and tax > 0:
        return nearest_supported_rate(round_money(tax * Decimal("100") / taxable))
    return nearest_supported_rate(rate)


def nearest_supported_rate(rate: Decimal) -> Decimal:
    if rate in SUPPORTED_RATES:
        return rate
    nearest = min(SUPPORTED_RATES, key=lambda slab: abs(slab - rate))
    return nearest if abs(nearest - rate) <= Decimal("0.25") else rate


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
    txn = normalize_tax_split(txn)
    if isinstance(txn.get("invoice_date"), str):
        text_value = txn["invoice_date"].strip()
        dayfirst = not text_value[:4].isdigit()
        parsed = pd.to_datetime(text_value, errors="coerce", dayfirst=dayfirst)
        txn["invoice_date"] = None if pd.isna(parsed) else parsed.date()
    errors = validate_transaction(txn)
    txn["validation_status"] = "error" if errors else "valid"
    txn["validation_errors"] = "; ".join(errors) if errors else None
    return txn
