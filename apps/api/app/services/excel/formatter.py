from __future__ import annotations

from typing import Any

from app.services.validation import money
from app.utils.states import STATE_CODES


EXCEL_FORMULA_PREFIXES = ("=", "+", "-", "@")
ETIN_NAMES = {
    "07AARCM9332R1CQ": "meesho",
    "07AACCF0683K1CU": "flipkart",
    "07AAICA3918J1CV": "amazon",
}
STATE_LABELS = {
    "26": "Dadra & Nagar Haveli & Daman & Diu",
    "35": "Andaman & Nicobar Islands",
}


def safe_excel_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(EXCEL_FORMULA_PREFIXES):
        return "'" + value
    return value


def amount(value: Any) -> float:
    return float(money(value))


def state_label(code: object) -> str:
    state_code = str(code or "").zfill(2)
    name = STATE_LABELS.get(state_code) or STATE_CODES.get(state_code) or ""
    return f"{state_code}-{name}" if name else state_code


def operator_name(etin: str) -> str:
    return ETIN_NAMES.get(etin, etin)
