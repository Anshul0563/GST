from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import re
from typing import Any

from app.services.validation import (
    SUPPORTED_RATES,
    money,
    validate_gstin,
    validate_period,
)

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


def split_tax_evenly(total_tax: Decimal) -> tuple[Decimal, Decimal]:
    half = money(total_tax / Decimal("2"))
    return half, money(total_tax - half)


def valid_for_b2cs(row: dict[str, Any]) -> bool:
    if row.get("validation_status") != "valid":
        return False
    if not row.get("buyer_state_code") or not row.get("invoice_no"):
        return False
    rate = money(row.get("gst_rate"))
    taxable = money(row.get("taxable_value"))
    total_tax = (
        money(row.get("igst"))
        + money(row.get("cgst"))
        + money(row.get("sgst"))
        + money(row.get("cess"))
    )
    return rate != Decimal("0.00") and not (
        taxable == Decimal("0.00") and total_tax == Decimal("0.00")
    )


def valid_for_supeco(row: dict[str, Any]) -> bool:
    return valid_for_b2cs(row) and bool(row.get("etin"))


def valid_for_doc_issue(row: dict[str, Any]) -> bool:
    if row.get("validation_status") not in {"valid", "skipped"}:
        return False
    if not row.get("invoice_no"):
        return False
    return str(row.get("doc_type") or "").lower() in DOC_NUM


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


def document_number(invoice_no: str) -> int | None:
    match = re.search(r"(\d+)(?!.*\d)", str(invoice_no))
    return int(match.group(1)) if match else None


def split_document_ranges(values: list[str]) -> list[list[str]]:
    if not values:
        return []
    ordered = sorted(values, key=document_sort_key)
    ranges: list[list[str]] = []
    current = [ordered[0]]
    previous_number = document_number(ordered[0])
    for value in ordered[1:]:
        current_number = document_number(value)
        if (
            previous_number is not None
            and current_number is not None
            and current_number == previous_number + 1
        ):
            current.append(value)
        else:
            ranges.append(current)
            current = [value]
        previous_number = current_number
    ranges.append(current)
    return ranges


def document_group_key(row: dict[str, Any], invoice_no: str) -> str:
    platform = str(row.get("platform") or "unknown").lower()
    doc_type = str(row.get("doc_type") or "invoice").lower()
    source = str(row.get("source_file") or "").lower()
    if platform == "flipkart":
        if "sales report" in source:
            return f"flipkart:sales:{doc_type}"
        if "cash back report" in source:
            return f"flipkart:cashback:{doc_type}"
    return f"{platform}:{document_series_key(invoice_no)}"


def build_b2cs(gstin: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, Decimal, str, str], dict[str, Decimal]] = defaultdict(
        lambda: {
            "txval": Decimal("0.00"),
            "iamt": Decimal("0.00"),
            "camt": Decimal("0.00"),
            "samt": Decimal("0.00"),
            "csamt": Decimal("0.00"),
        }
    )
    for row in rows:
        if not valid_for_b2cs(row):
            continue
        sply_ty = classify_supply(gstin, row.get("buyer_state_code"))
        key = (
            sply_ty,
            money(row.get("gst_rate")),
            str(row.get("buyer_state_code")),
            "OE",
        )
        groups[key]["txval"] += money(row.get("taxable_value"))
        groups[key]["iamt"] += money(row.get("igst"))
        groups[key]["camt"] += money(row.get("cgst"))
        groups[key]["samt"] += money(row.get("sgst"))
        groups[key]["csamt"] += money(row.get("cess"))

    output: list[dict[str, Any]] = []
    for (sply_ty, rate, pos, typ), amounts in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][2], item[0][1])
    ):
        total_tax = (
            amounts["iamt"] + amounts["camt"] + amounts["samt"] + amounts["csamt"]
        )
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
            intra_tax = amounts["camt"] + amounts["samt"]
            camt, samt = split_tax_evenly(intra_tax)
            base["camt"] = json_amount(camt)
            base["samt"] = json_amount(samt)
            base["csamt"] = json_amount(amounts["csamt"])
        output.append(base)
    return output


def build_supeco(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "suppval": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "cess": Decimal("0.00"),
        }
    )
    for row in rows:
        if not valid_for_supeco(row):
            continue
        etin = str(row.get("etin"))
        groups[etin]["suppval"] += money(row.get("taxable_value"))
        groups[etin]["igst"] += money(row.get("igst"))
        groups[etin]["cgst"] += money(row.get("cgst"))
        groups[etin]["sgst"] += money(row.get("sgst"))
        groups[etin]["cess"] += money(row.get("cess"))
    return [
        {
            "etin": etin,
            "suppval": json_amount(amounts["suppval"]),
            "igst": json_amount(amounts["igst"]),
            "cgst": json_amount(split_tax_evenly(amounts["cgst"] + amounts["sgst"])[0]),
            "sgst": json_amount(split_tax_evenly(amounts["cgst"] + amounts["sgst"])[1]),
            "cess": json_amount(amounts["cess"]),
            "flag": "N",
        }
        for etin, amounts in sorted(groups.items())
    ]


def build_doc_issue(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        if not valid_for_doc_issue(row):
            continue
        doc_type = str(row.get("doc_type") or "invoice").lower()
        if doc_type not in DOC_NUM:
            continue
        invoice_no = str(row.get("invoice_no") or "").strip()
        if not invoice_no:
            continue
        platform = str(row.get("platform") or "unknown").lower()
        grouped[(doc_type, platform, document_group_key(row, invoice_no))].add(
            invoice_no
        )

    doc_det: list[dict[str, Any]] = []
    for doc_type in ("invoice", "credit_note", "debit_note"):
        series = [
            (key, sorted(values, key=document_sort_key))
            for key, values in grouped.items()
            if key[0] == doc_type
        ]
        if not series:
            continue
        docs = []
        for key, values in sorted(
            series, key=lambda item: document_sort_key(item[1][0])
        ):
            ranges = (
                [values]
                if str(key[2]).startswith("flipkart:")
                else split_document_ranges(values)
            )
            for item_range in ranges:
                docs.append(
                    {
                        "num": len(docs) + 1,
                        "from": item_range[0],
                        "to": item_range[-1],
                        "totnum": len(item_range),
                        "cancel": 0,
                        "net_issue": len(item_range),
                    }
                )
        doc_det.append(
            {"doc_num": DOC_NUM[doc_type], "doc_typ": DOC_TYP[doc_type], "docs": docs}
        )
    doc_det.sort(key=lambda item: [1, 5, 4].index(item["doc_num"]))
    return {"doc_det": doc_det}


def validate_doc_issue_ranges(doc_issue: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for section in doc_issue.get("doc_det", []):
        for doc in section.get("docs", []):
            start = document_number(str(doc.get("from") or ""))
            end = document_number(str(doc.get("to") or ""))
            totnum = int(doc.get("totnum") or 0)
            if (
                document_series_key(str(doc.get("from") or ""))
                == document_series_key(str(doc.get("to") or ""))
                and start is not None
                and end is not None
                and end >= start
            ):
                implied = end - start + 1
                if implied != totnum:
                    errors.append(
                        f"Document range {doc.get('from')} to {doc.get('to')} implies {implied} documents but totnum is {totnum}"
                    )
    return errors


def validate_gstr1_schema(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if list(payload.keys()) != [
        "gstin",
        "fp",
        "version",
        "hash",
        "b2cs",
        "supeco",
        "doc_issue",
    ]:
        errors.append("GSTR-1 top-level JSON keys drifted from accepted contract")
    if not validate_gstin(str(payload.get("gstin") or "")):
        errors.append("Invalid GSTIN in export payload")
    if not validate_period(str(payload.get("fp") or "")):
        errors.append("Invalid filing period in export payload")
    if payload.get("version") != GST_VERSION:
        errors.append("Invalid GST JSON version")
    if payload.get("hash") != "hash":
        errors.append('GST portal reference hash must be literal "hash"')
    supeco = payload.get("supeco")
    if not isinstance(supeco, dict) or set(supeco.keys()) != {"clttx"}:
        errors.append("SUPECO must contain only clttx")
    if "supeco_det" in (supeco or {}):
        errors.append("supeco_det is not allowed")
    doc_issue = payload.get("doc_issue")
    if not isinstance(doc_issue, dict) or set(doc_issue.keys()) != {"doc_det"}:
        errors.append("doc_issue must contain only doc_det")
    for item in payload.get("b2cs", []):
        expected_keys = {"sply_ty", "rt", "typ", "pos", "txval", "csamt"}
        if item.get("sply_ty") == "INTER":
            expected_keys.add("iamt")
        elif item.get("sply_ty") == "INTRA":
            expected_keys.update({"camt", "samt"})
        else:
            errors.append(f"Invalid B2CS supply type: {item.get('sply_ty')}")
            continue
        if set(item.keys()) != expected_keys:
            errors.append(f"B2CS key mismatch for POS {item.get('pos')}")
        if money(item.get("rt")) not in SUPPORTED_RATES or money(
            item.get("rt")
        ) == Decimal("0.00"):
            errors.append(
                f"Invalid/fake B2CS rate for POS {item.get('pos')}: {item.get('rt')}"
            )
        tax_total = (
            money(item.get("iamt"))
            + money(item.get("camt"))
            + money(item.get("samt"))
            + money(item.get("csamt"))
        )
        if money(item.get("txval")) == Decimal("0.00") and tax_total == Decimal("0.00"):
            errors.append(f"Fake zero B2CS row for POS {item.get('pos')}")
        if item.get("sply_ty") == "INTRA" and abs(
            money(item.get("camt")) - money(item.get("samt"))
        ) > Decimal("0.01"):
            errors.append(
                f"INTRA CGST/SGST split differs by more than 0.01 for POS {item.get('pos')}"
            )
    for section in payload.get("doc_issue", {}).get("doc_det", []):
        if set(section.keys()) != {"doc_num", "doc_typ", "docs"}:
            errors.append("doc_issue section key mismatch")
        if DOC_TYP.get(
            next(
                (
                    key
                    for key, value in DOC_NUM.items()
                    if value == section.get("doc_num")
                ),
                "",
            )
        ) != section.get("doc_typ"):
            errors.append(f"doc_typ mismatch for doc_num {section.get('doc_num')}")
        for doc in section.get("docs", []):
            if set(doc.keys()) != {
                "num",
                "from",
                "to",
                "totnum",
                "cancel",
                "net_issue",
            }:
                errors.append(f"doc_issue docs key mismatch for {doc.get('from')}")
            if int(doc.get("net_issue") or 0) != int(doc.get("totnum") or 0) - int(
                doc.get("cancel") or 0
            ):
                errors.append(
                    f"doc_issue net_issue mismatch for {doc.get('from')} to {doc.get('to')}"
                )
    return errors


def gstr1_generation_report(
    payload: dict[str, Any], source_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    uploaded_platforms = sorted(
        {
            str(row.get("platform") or "unknown")
            for row in source_rows
            if row.get("platform")
        }
    )
    valid_rows = [row for row in source_rows if valid_for_gstr(row)]
    valid_by_platform = {
        platform: sum(1 for row in valid_rows if row.get("platform") == platform)
        for platform in uploaded_platforms
    }
    supeco_etins = [
        row.get("etin") for row in payload.get("supeco", {}).get("clttx", [])
    ]
    warnings = []
    for platform, count in valid_by_platform.items():
        if count == 0:
            if platform == "meesho":
                warnings.append(
                    f"No valid Meesho rows found for period {payload.get('fp')}"
                )
            else:
                warnings.append(
                    f"No valid {platform.title()} rows found for period {payload.get('fp')}"
                )

    errors = validate_gstr1_schema(payload)
    errors.extend(validate_doc_issue_ranges(payload.get("doc_issue", {})))
    valid_etins = sorted(
        {str(row.get("etin")) for row in valid_rows if row.get("etin")}
    )
    missing_etins = [etin for etin in valid_etins if etin not in supeco_etins]
    for etin in missing_etins:
        platforms = sorted(
            {
                str(row.get("platform"))
                for row in valid_rows
                if str(row.get("etin")) == etin
            }
        )
        errors.append(
            f"Valid rows for {', '.join(platforms)} have ETIN {etin}, but SUPECO clttx is missing it"
        )
    if (
        "meesho" in uploaded_platforms
        and valid_by_platform.get("meesho", 0) > 0
        and "07AARCM9332R1CQ" not in supeco_etins
    ):
        errors.append(
            "Uploaded Meesho rows are valid, but Meesho SUPECO summary is missing"
        )

    return {
        "uploaded_platforms": uploaded_platforms,
        "valid_rows_per_platform": valid_by_platform,
        "supeco_etins": supeco_etins,
        "warnings": warnings,
        "errors": errors,
    }


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
