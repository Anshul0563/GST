from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


EXPECTED_TOP_KEYS = {
    "gstin",
    "fp",
    "version",
    "hash",
    "b2cs",
    "supeco",
    "doc_issue",
    "nil",
    "hsn",
}
VALID_RATES = {
    Decimal("0"),
    Decimal("0.1"),
    Decimal("0.25"),
    Decimal("1"),
    Decimal("1.5"),
    Decimal("3"),
    Decimal("5"),
    Decimal("6"),
    Decimal("7.5"),
    Decimal("12"),
    Decimal("18"),
    Decimal("28"),
}
DOC_TYPES = {
    1: "Invoices for outward supply",
    4: "Debit Note",
    5: "Credit Note",
}
HSN_ALLOWED_KEYS = {
    "num",
    "hsn_sc",
    "desc",
    "user_desc",
    "uqc",
    "qty",
    "rt",
    "txval",
    "iamt",
    "camt",
    "samt",
    "csamt",
}
HSN_REQUIRED_KEYS = {"num", "hsn_sc", "desc", "uqc", "qty", "rt", "txval"}
TWO_PLACES = Decimal("0.01")
DOC_SERIAL_RE = re.compile(r"^[A-Za-z0-9/-]{1,16}$")


def money(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def number(value: Any) -> int | float:
    amount = Decimal(str(value))
    if amount == amount.to_integral_value():
        return int(amount)
    return float(amount)


def numeric_string_to_int(value: Any) -> Any:
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value)
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    return value


def normalize_for_json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return number(value)
    if isinstance(value, list):
        return [normalize_for_json(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_for_json(item) for key, item in value.items()}
    return value


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_float=Decimal,
        parse_int=Decimal,
    )


def fix_payload(payload: dict[str, Any]) -> dict[str, Any]:
    fixed = deepcopy(payload)

    hsn = fixed.get("hsn")
    if isinstance(hsn, dict) and "data" in hsn:
        fixed["hsn"] = {
            "hsn_b2b": [],
            "hsn_b2c": [
                {key: value for key, value in item.items() if key != "val"}
                for item in hsn.get("data", [])
                if isinstance(item, dict)
            ],
        }
    elif isinstance(hsn, dict):
        fixed["hsn"] = {
            "hsn_b2b": [
                {key: value for key, value in item.items() if key != "val"}
                for item in hsn.get("hsn_b2b", [])
                if isinstance(item, dict)
            ],
            "hsn_b2c": [
                {key: value for key, value in item.items() if key != "val"}
                for item in hsn.get("hsn_b2c", [])
                if isinstance(item, dict)
            ],
        }

    doc_issue = fixed.get("doc_issue", {})
    for section in doc_issue.get("doc_det", []) if isinstance(doc_issue, dict) else []:
        section["doc_num"] = numeric_string_to_int(section.get("doc_num"))
        cleaned_docs = []
        for doc in section.get("docs", []):
            doc_from = str(doc.get("from") or "").strip()
            doc_to = str(doc.get("to") or "").strip()
            if not DOC_SERIAL_RE.fullmatch(doc_from) or not DOC_SERIAL_RE.fullmatch(doc_to):
                continue
            for field in ("num", "totnum", "cancel", "net_issue"):
                doc[field] = numeric_string_to_int(doc.get(field))
            cleaned_docs.append(doc)
        for index, doc in enumerate(cleaned_docs, start=1):
            doc["num"] = index
        section["docs"] = cleaned_docs

    hsn = fixed.get("hsn")
    if isinstance(hsn, dict):
        for section in ("hsn_b2b", "hsn_b2c"):
            for row in hsn.get(section, []):
                if isinstance(row, dict) and not str(row.get("desc") or "").strip():
                    row["desc"] = "Goods"

    return fixed


def totals(payload: dict[str, Any]) -> dict[str, Decimal]:
    b2cs = payload.get("b2cs", [])
    return {
        "taxable": money(sum((money(row.get("txval")) for row in b2cs), Decimal("0"))),
        "igst": money(sum((money(row.get("iamt")) for row in b2cs), Decimal("0"))),
        "cgst": money(sum((money(row.get("camt")) for row in b2cs), Decimal("0"))),
        "sgst": money(sum((money(row.get("samt")) for row in b2cs), Decimal("0"))),
        "cess": money(sum((money(row.get("csamt")) for row in b2cs), Decimal("0"))),
    }


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if set(payload) - EXPECTED_TOP_KEYS:
        errors.append(f"unsupported top-level keys: {sorted(set(payload) - EXPECTED_TOP_KEYS)}")
    if payload.get("gstin") != "07TCRPS8655B1ZK":
        errors.append("unexpected gstin")
    if payload.get("fp") != "092026":
        errors.append("unexpected filing period")
    if payload.get("version") != "GST3.1.6":
        errors.append("unexpected GST version")
    if payload.get("hash") != "hash":
        errors.append('hash must be literal "hash"')

    for index, row in enumerate(payload.get("b2cs", []), start=1):
        expected = {"sply_ty", "rt", "typ", "pos", "txval", "csamt"}
        if row.get("sply_ty") == "INTER":
            expected.add("iamt")
        elif row.get("sply_ty") == "INTRA":
            expected.update({"camt", "samt"})
        else:
            errors.append(f"b2cs[{index}] invalid sply_ty")
        if set(row) != expected:
            errors.append(f"b2cs[{index}] key mismatch: {sorted(row)}")
        if Decimal(str(row.get("rt"))) not in VALID_RATES:
            errors.append(f"b2cs[{index}] invalid rate")
        if row.get("typ") not in {"E", "OE"}:
            errors.append(f"b2cs[{index}] invalid typ")
        if not re.fullmatch(r"\d{2}", str(row.get("pos", ""))):
            errors.append(f"b2cs[{index}] invalid pos")

    nil = payload.get("nil")
    if nil is not None:
        if not isinstance(nil, dict) or set(nil) != {"inv"}:
            errors.append("nil must contain only inv")
        for index, row in enumerate(nil.get("inv", []) if isinstance(nil, dict) else [], start=1):
            if set(row) != {"sply_ty", "nil_amt", "expt_amt", "ngsup_amt"}:
                errors.append(f"nil.inv[{index}] key mismatch")

    supeco = payload.get("supeco")
    if not isinstance(supeco, dict) or set(supeco) != {"clttx"}:
        errors.append("supeco must contain only clttx")
    for index, row in enumerate(supeco.get("clttx", []) if isinstance(supeco, dict) else [], start=1):
        if set(row) != {"etin", "suppval", "igst", "cgst", "sgst", "cess", "flag"}:
            errors.append(f"supeco.clttx[{index}] key mismatch")
        if row.get("flag") not in {"N", "U", "D", "E"}:
            errors.append(f"supeco.clttx[{index}] invalid flag")

    doc_issue = payload.get("doc_issue")
    if not isinstance(doc_issue, dict) or set(doc_issue) != {"doc_det"}:
        errors.append("doc_issue must contain only doc_det")
    for section in doc_issue.get("doc_det", []) if isinstance(doc_issue, dict) else []:
        doc_num = section.get("doc_num")
        if not isinstance(doc_num, int) or doc_num not in DOC_TYPES:
            errors.append(f"doc_issue invalid doc_num: {doc_num!r}")
        elif section.get("doc_typ") != DOC_TYPES[doc_num]:
            errors.append(f"doc_issue doc_typ mismatch for doc_num {doc_num}")
        if set(section) != {"doc_num", "doc_typ", "docs"}:
            errors.append(f"doc_issue section key mismatch for {doc_num}")
        for doc in section.get("docs", []):
            if set(doc) != {"num", "from", "to", "totnum", "cancel", "net_issue"}:
                errors.append(f"doc_issue doc key mismatch for {doc.get('from')}")
            for field in ("num", "totnum", "cancel", "net_issue"):
                if not isinstance(doc.get(field), int):
                    errors.append(f"doc_issue {field} must be number for {doc.get('from')}")
            if isinstance(doc.get("totnum"), int) and isinstance(doc.get("cancel"), int):
                if doc.get("net_issue") != doc["totnum"] - doc["cancel"]:
                    errors.append(f"doc_issue net_issue mismatch for {doc.get('from')}")
            for field in ("from", "to"):
                value = str(doc.get(field) or "")
                if not DOC_SERIAL_RE.fullmatch(value):
                    errors.append(f"doc_issue {field} invalid serial: {value!r}")

    hsn = payload.get("hsn")
    if hsn is not None:
        if not isinstance(hsn, dict) or set(hsn) != {"hsn_b2b", "hsn_b2c"}:
            errors.append("hsn must contain only hsn_b2b and hsn_b2c")
        for section in ("hsn_b2b", "hsn_b2c"):
            rows = hsn.get(section, []) if isinstance(hsn, dict) else []
            if not isinstance(rows, list):
                errors.append(f"hsn.{section} must be list")
                continue
            for index, row in enumerate(rows, start=1):
                if set(row) - HSN_ALLOWED_KEYS:
                    errors.append(f"hsn.{section}[{index}] unsupported keys: {sorted(set(row) - HSN_ALLOWED_KEYS)}")
                if not HSN_REQUIRED_KEYS.issubset(row):
                    errors.append(f"hsn.{section}[{index}] missing mandatory keys")
                if not str(row.get("desc") or "").strip():
                    errors.append(f"hsn.{section}[{index}] desc blank")

    expected_totals = {
        "taxable": Decimal("40950.68"),
        "igst": Decimal("1589.25"),
        "cgst": Decimal("29.99"),
        "sgst": Decimal("29.99"),
    }
    actual_totals = totals(payload)
    for field, expected in expected_totals.items():
        if actual_totals[field] != expected:
            errors.append(f"{field} total changed: {actual_totals[field]} != {expected}")
    if actual_totals["igst"] + actual_totals["cgst"] + actual_totals["sgst"] != Decimal("1649.23"):
        errors.append("total GST changed")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    original = load_json(args.input)
    fixed = fix_payload(original)
    errors = validate_payload(fixed)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(normalize_for_json(fixed), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("PASS")
    print(f"output={args.output}")
    print(
        "b2cs_totals="
        + json.dumps({key: str(value) for key, value in totals(fixed).items()}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
