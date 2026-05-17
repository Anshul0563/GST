import re
from decimal import Decimal, ROUND_HALF_UP

from app.utils.states import STATE_CODES


GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
SUPPORTED_RATES = {Decimal("0"), Decimal("0.1"), Decimal("0.25"), Decimal("1"), Decimal("1.5"), Decimal("3"), Decimal("5"), Decimal("6"), Decimal("12"), Decimal("18"), Decimal("28")}


def money(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        cleaned = str(value).replace(",", "").replace("₹", "").strip()
        if cleaned in {"", "-", "nan", "None"}:
            return Decimal("0.00")
        decimal_value = Decimal(cleaned)
    return decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_gstin(gstin: str) -> bool:
    return bool(GSTIN_RE.match(gstin.upper()))


def validate_period(period: str) -> bool:
    return bool(re.match(r"^(0[1-9]|1[0-2])20[0-9]{2}$", period))


def validate_transaction(txn: dict) -> list[str]:
    errors: list[str] = []
    if not validate_gstin(str(txn.get("gstin", ""))):
        errors.append("Invalid GSTIN")
    if not validate_period(str(txn.get("filing_period", ""))):
        errors.append("Invalid filing period")
    if not txn.get("buyer_state_code"):
        errors.append("Missing POS")
    elif txn["buyer_state_code"] not in STATE_CODES:
        errors.append("Invalid state code")
    if not txn.get("invoice_no"):
        errors.append("Missing invoice number")
    rate = money(txn.get("gst_rate"))
    if rate not in SUPPORTED_RATES:
        errors.append("Unsupported GST rate")
    if not txn.get("etin"):
        errors.append("Missing ETIN")
    taxable = money(txn.get("taxable_value"))
    expected = (taxable * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    actual = money(txn.get("igst")) + money(txn.get("cgst")) + money(txn.get("sgst")) + money(txn.get("cess"))
    if abs(expected - actual) > Decimal("1.00"):
        errors.append("Tax mismatch beyond Rs. 1 tolerance")
    return errors

