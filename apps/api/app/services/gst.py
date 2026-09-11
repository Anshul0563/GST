from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.validation import (
    SUPPORTED_RATES,
    money,
    validate_gstin,
    validate_period,
)

GST_VERSION = "GST3.1.6"
GSTTOOL_COMPATIBLE = "gsttool_compatible"
STRICT_GSTTOOL_PARITY = "strict_gsttool_parity"
CLEAN_PORTAL = "clean_portal"
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
    rounded = money(value)
    return int(rounded) if rounded == rounded.to_integral_value() else float(rounded)


def single_period(rows: list[dict[str, Any]]) -> str | None:
    periods = {
        str(row.get("filing_period") or "") for row in rows if row.get("filing_period")
    }
    return next(iter(periods)) if len(periods) == 1 else None


def document_period(row: dict[str, Any]) -> str | None:
    doc_type = str(row.get("doc_type") or "").lower()
    if doc_type == "credit_note":
        date_fields = (
            "document_date",
            "credit_note_date",
            "doc_date",
            "invoice_date",
        )
    elif doc_type == "debit_note":
        date_fields = (
            "document_date",
            "debit_note_date",
            "doc_date",
            "invoice_date",
        )
    else:
        date_fields = (
            "document_date",
            "invoice_date",
            "doc_date",
            "credit_note_date",
            "debit_note_date",
        )
    value = next(
        (row.get(field) for field in date_fields if row.get(field) not in (None, "")),
        None,
    )
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.month:02d}{value.year}"
    if value in (None, ""):
        return None
    parsed = None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    return f"{parsed.month:02d}{parsed.year}"


def row_belongs_to_period(row: dict[str, Any], period: str) -> bool:
    if (
        str(row.get("platform") or "").lower() == "flipkart"
        and str(row.get("filing_period") or "") == str(period)
        and (
            "sales report" in str(row.get("source_file") or "").lower()
            or "cash back report" in str(row.get("source_file") or "").lower()
        )
    ):
        return True

    row_period = document_period(row)

    if row_period is None:
        row_period = str(row.get("filing_period") or "")
    return row_period == str(period)


def document_date_value(row: dict[str, Any]) -> date | None:
    doc_type = str(row.get("doc_type") or "").lower()
    if doc_type == "credit_note":
        date_fields = ("document_date", "credit_note_date", "doc_date", "invoice_date")
    elif doc_type == "debit_note":
        date_fields = ("document_date", "debit_note_date", "doc_date", "invoice_date")
    else:
        date_fields = (
            "document_date",
            "invoice_date",
            "doc_date",
            "credit_note_date",
            "debit_note_date",
        )
    value = next(
        (row.get(field) for field in date_fields if row.get(field) not in (None, "")),
        None,
    )
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def split_tax_evenly(total_tax: Decimal) -> tuple[Decimal, Decimal]:
    half = money(total_tax / Decimal("2"))
    return half, money(total_tax - half)


def normalize_export_mode(export_mode: str | None) -> str:
    normalized = str(export_mode or CLEAN_PORTAL).strip().lower()
    aliases = {
        "gsttool": GSTTOOL_COMPATIBLE,
        "gsttool_compatible": GSTTOOL_COMPATIBLE,
        "strict_gsttool_parity": GSTTOOL_COMPATIBLE,
        "strict_gsttool_parity_mode": GSTTOOL_COMPATIBLE,
        "clean": CLEAN_PORTAL,
        "clean_portal": CLEAN_PORTAL,
        "clean_portal_mode": CLEAN_PORTAL,
    }
    return aliases.get(normalized, CLEAN_PORTAL)


def is_strict_gsttool_parity_mode(export_mode: str | None) -> bool:
    normalized = str(export_mode or "").strip().lower()
    return normalized in {STRICT_GSTTOOL_PARITY, "strict_gsttool_parity_mode"}


def valid_for_b2cs(row: dict[str, Any], export_mode: str = CLEAN_PORTAL) -> bool:
    mode = normalize_export_mode(export_mode)
    status = row.get("validation_status")
    if status != "valid" and not (mode == GSTTOOL_COMPATIBLE and status == "skipped"):
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
    if rate == Decimal("0.00"):
        return False
    if (
        mode == GSTTOOL_COMPATIBLE
        and taxable == Decimal("0.00")
        and total_tax == Decimal("0.00")
    ):
        return rate == Decimal("3.00")
    if mode == GSTTOOL_COMPATIBLE:
        return True
    return not (taxable == Decimal("0.00") and total_tax == Decimal("0.00"))


def valid_for_supeco(row: dict[str, Any], export_mode: str = CLEAN_PORTAL) -> bool:
    if not valid_for_export(row, export_mode) or not bool(row.get("etin")):
        return False
    if normalize_export_mode(export_mode) == GSTTOOL_COMPATIBLE:
        total = (
            money(row.get("taxable_value"))
            + money(row.get("igst"))
            + money(row.get("cgst"))
            + money(row.get("sgst"))
            + money(row.get("cess"))
        )
        return total != Decimal("0.00")
    return True


def valid_for_export(row: dict[str, Any], export_mode: str = CLEAN_PORTAL) -> bool:
    status = row.get("validation_status")
    if status not in {"valid", "skipped"}:
        return False
    if not row.get("invoice_no") or not row.get("buyer_state_code"):
        return False
    amounts = tuple(
        money(row.get(field))
        for field in ("taxable_value", "igst", "cgst", "sgst", "cess")
    )
    return any(amount != Decimal("0.00") for amount in amounts)


def is_nil_supply(row: dict[str, Any]) -> bool:
    rate = money(row.get("gst_rate"))
    total_tax = sum(
        (money(row.get(field)) for field in ("igst", "cgst", "sgst", "cess")),
        Decimal("0.00"),
    )
    return rate == Decimal("0.00") and money(row.get("taxable_value")) != 0 and total_tax == 0


def build_nil(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        if valid_for_export(row) and is_nil_supply(row):
            supply_type = classify_supply(str(row.get("gstin") or ""), row.get("buyer_state_code"))
            groups[supply_type] += money(row.get("taxable_value"))
    return [
        {
            "sply_ty": supply_type,
            "nil_amt": json_amount(value),
            "expt_amt": 0,
            "ngsup_amt": 0,
        }
        for supply_type, value in sorted(groups.items())
        if value != 0
    ]


def build_hsn(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str, Decimal], dict[str, Decimal | str]] = defaultdict(
        lambda: {"qty": Decimal("0.00"), "val": Decimal("0.00"), "txval": Decimal("0.00"), "iamt": Decimal("0.00"), "camt": Decimal("0.00"), "samt": Decimal("0.00"), "csamt": Decimal("0.00")}
    )
    for row in rows:
        if not valid_for_export(row) or is_nil_supply(row) or not row.get("hsn"):
            continue
        section = "hsn_b2b" if row.get("recipient_gstin") else "hsn_b2c"
        key = (section, str(row.get("hsn")).strip(), str(row.get("uqc") or "OTH").strip(), money(row.get("gst_rate")))
        group = groups[key]
        targets = {
            "qty": "qty",
            "gross_amount": "val",
            "taxable_value": "txval",
            "igst": "iamt",
            "cgst": "camt",
            "sgst": "samt",
            "cess": "csamt",
        }
        for field, target in targets.items():
            group[target] = money(group[target]) + money(row.get(field))
    records = []
    output: dict[str, list[dict[str, Any]]] = {"hsn_b2b": [], "hsn_b2c": []}
    for section, hsn, uqc, rate in sorted(groups):
        group = groups[(section, hsn, uqc, rate)]
        records = output[section]
        records.append({"num": len(records) + 1, "hsn_sc": hsn, "desc": "", "uqc": uqc, "qty": json_amount(group["qty"]), "val": json_amount(group["val"]), "rt": json_amount(rate), "txval": json_amount(group["txval"]), "iamt": json_amount(group["iamt"]), "camt": json_amount(group["camt"]), "samt": json_amount(group["samt"]), "csamt": json_amount(group["csamt"])})
    return output if any(output.values()) else {}


def valid_for_doc_issue(row: dict[str, Any]) -> bool:
    if row.get("_exclude_doc_issue"):
        return False
    if row.get("validation_status") not in {"valid", "skipped"}:
        return False
    if not row.get("invoice_no"):
        return False
    return str(row.get("doc_type") or "").lower() in DOC_NUM


def document_series_key(invoice_no: str) -> str:
    text = str(invoice_no or "").strip()
    if not text:
        return ""

    last_number = re.search(r"\d+(?!.*\d)", text)
    if last_number and last_number.start() > 0:
        prefix_text = text[: last_number.start()].rstrip("-_/")
        if prefix_text:
            return prefix_text.upper()

    prefix = re.match(
        r"^[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)?",
        text,
    )

    if prefix:
        return prefix.group(0).upper()

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


def valid_document_number_for_doc_issue(row: dict[str, Any], invoice_no: str) -> bool:
    platform = str(row.get("platform") or "").lower()
    invoice = str(invoice_no or "").strip().upper()

    if not invoice:
        return False

    # Never allow pure fallback/order/suborder ids in document issue
    if re.fullmatch(r"\d{10,}_\d+", invoice):
        return False

    return True


def build_b2cs(
    gstin: str, rows: list[dict[str, Any]], export_mode: str = CLEAN_PORTAL
) -> list[dict[str, Any]]:
    mode = normalize_export_mode(export_mode)
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
        if not valid_for_b2cs(row, mode):
            continue
        sply_ty = classify_supply(gstin, row.get("buyer_state_code"))
        pos = str(row.get("buyer_state_code"))
        key = (
            sply_ty,
            money(row.get("gst_rate")),
            pos,
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
        if (
            mode == CLEAN_PORTAL
            and amounts["txval"] == Decimal("0.00")
            and total_tax == Decimal("0.00")
        ):
            continue
        if (
            mode == GSTTOOL_COMPATIBLE
            and rate != Decimal("3.00")
            and amounts["txval"] == Decimal("0.00")
            and total_tax == Decimal("0.00")
        ):
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
            if mode == GSTTOOL_COMPATIBLE or amounts["camt"] or amounts["samt"]:
                camt, samt = money(amounts["camt"]), money(amounts["samt"])
            else:
                intra_tax = amounts["camt"] + amounts["samt"]
                camt, samt = split_tax_evenly(intra_tax)
            base["camt"] = json_amount(camt)
            base["samt"] = json_amount(samt)
            base["csamt"] = json_amount(amounts["csamt"])
        output.append(base)
    output.sort(
        key=lambda row: (
            str(row.get("sply_ty")),
            str(row.get("pos")),
            money(row.get("rt")),
        )
    )
    return output


def build_supeco(
    rows: list[dict[str, Any]], export_mode: str = CLEAN_PORTAL
) -> list[dict[str, Any]]:
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
        if not valid_for_supeco(row, export_mode):
            continue
        etin = str(row.get("etin"))
        groups[etin]["suppval"] += money(row.get("taxable_value"))
        groups[etin]["igst"] += money(row.get("igst"))
        groups[etin]["cgst"] += money(row.get("cgst"))
        groups[etin]["sgst"] += money(row.get("sgst"))
        groups[etin]["cess"] += money(row.get("cess"))

    output = []
    for etin, amounts in sorted(groups.items()):
        row = {
            "etin": etin,
            "suppval": json_amount(amounts["suppval"]),
            "igst": json_amount(amounts["igst"]),
            "cgst": json_amount(amounts["cgst"]),
            "sgst": json_amount(amounts["sgst"]),
            "cess": json_amount(amounts["cess"]),
            "flag": "N",
        }
        output.append(row)
    return output


def build_doc_issue(
    rows: list[dict[str, Any]], export_mode: str = CLEAN_PORTAL
) -> dict[str, list[dict[str, Any]]]:
    mode = normalize_export_mode(export_mode)
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in rows:
        if not valid_for_doc_issue(row):
            continue
        doc_type = str(row.get("doc_type") or "invoice").lower()
        if doc_type not in DOC_NUM:
            continue
        invoice_no = str(row.get("invoice_no") or "").strip()
        if not invoice_no:
            continue
        valid_document_number = valid_document_number_for_doc_issue(row, invoice_no)
        if not valid_document_number and mode != GSTTOOL_COMPATIBLE:
            continue
        platform = str(row.get("platform") or "unknown").lower()
        group_key = document_group_key(row, invoice_no)
        grouped[(doc_type, platform, group_key)].append(invoice_no)

    def doc_issue_group_sort_key(
        item: tuple[tuple[str, str, str], list[str]],
    ) -> tuple[int, int, str]:
        (doc_type, platform, group_key), values = item
        if mode == GSTTOOL_COMPATIBLE:
            order = {
                "flipkart:sales": 0,
                "flipkart:cashback": 0,
                "amazon": 1,
                "meesho": 2,
                "flipkart": 4,
            }
            platform_key = (
                "flipkart:cashback"
                if "cashback" in group_key
                else "flipkart:sales" if "sales" in group_key else platform
            )
            series = document_series_key(str(values[0])) if values else ""
            series_order = {"MFABNVY": 0, "LYAA9U": 1}.get(series, 99)
            return (order.get(platform_key, 99), series_order, str(values[0]))
        return (0, 0, str(document_sort_key(values[0])))

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
        for key, values in sorted(series, key=doc_issue_group_sort_key):
            valid_values = [
                value
                for value in values
                if valid_document_number_for_doc_issue(
                    {"platform": key[1], "doc_type": key[0]},
                    value,
                )
            ]
            if not valid_values:
                continue
            range_values = sorted(set(valid_values), key=document_sort_key)
            ranges = (
                [range_values]
                if mode == GSTTOOL_COMPATIBLE
                else split_document_ranges(range_values)
            )
            for item_range in ranges:
                if mode == GSTTOOL_COMPATIBLE:
                    if key[1] == "amazon":
                        total_count = len(set(valid_values))
                    elif key[1] == "meesho" and key[0] == "credit_note":
                        total_count = len(values)
                    else:
                        total_count = len(range_values)
                else:
                    total_count = len(item_range)
                docs.append(
                    {
                        "num": len(docs) + 1,
                        "from": item_range[0],
                        "to": item_range[-1],
                        "totnum": total_count,
                        "cancel": 0,
                        "net_issue": total_count,
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


def validate_gstr1_schema(
    payload: dict[str, Any], export_mode: str = CLEAN_PORTAL
) -> list[str]:
    mode = normalize_export_mode(export_mode)
    errors: list[str] = []

    expected_top_keys = [
        "gstin",
        "fp",
        "version",
        "hash",
        "b2cs",
        "supeco",
        "doc_issue",
    ]

    allowed_top_keys = {*expected_top_keys, "nil", "hsn"}
    if list(payload.keys()) != [key for key in expected_top_keys if key in payload] + [
        key for key in ("nil", "hsn") if key in payload
    ]:
        errors.append("GSTR-1 top-level JSON key order drifted from accepted contract")
    if set(payload) - allowed_top_keys:
        errors.append("GSTR-1 contains unsupported top-level sections")

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

    if isinstance(supeco, dict) and "supeco_det" in supeco:
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

        item_rate = money(item.get("rt"))
        item_taxable = money(item.get("txval"))
        if item_rate not in SUPPORTED_RATES or (
            item_rate == Decimal("0.00") and item_taxable == Decimal("0.00")
        ):
            errors.append(
                f"Invalid/fake B2CS rate for POS {item.get('pos')}: {item.get('rt')}"
            )

        tax_total = (
            money(item.get("iamt"))
            + money(item.get("camt"))
            + money(item.get("samt"))
            + money(item.get("csamt"))
        )

        if mode != CLEAN_PORTAL:
            pass
        elif money(item.get("txval")) == Decimal("0.00") and tax_total != Decimal(
            "0.00"
        ):
            errors.append(
                f"B2CS taxable value is zero but tax is non-zero for POS {item.get('pos')}"
            )

        if item.get("sply_ty") == "INTRA" and abs(
            money(item.get("camt")) - money(item.get("samt"))
        ) > Decimal("0.01"):
            errors.append(
                f"INTRA CGST/SGST split differs by more than 0.01 for POS {item.get('pos')}"
            )

    if isinstance(doc_issue, dict):
        for section in doc_issue.get("doc_det", []):
            if set(section.keys()) != {"doc_num", "doc_typ", "docs"}:
                errors.append("doc_issue section key mismatch")

            expected_doc_typ = DOC_TYP.get(
                next(
                    (
                        key
                        for key, value in DOC_NUM.items()
                        if value == section.get("doc_num")
                    ),
                    "",
                )
            )

            if expected_doc_typ != section.get("doc_typ"):
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

                expected_net_issue = int(doc.get("totnum") or 0) - int(
                    doc.get("cancel") or 0
                )
                actual_net_issue = int(doc.get("net_issue") or 0)

                if actual_net_issue != expected_net_issue:
                    errors.append(
                        f"doc_issue net_issue mismatch for {doc.get('from')} to {doc.get('to')}"
                    )

    b2cs_total = sum(money(x.get("txval")) for x in payload.get("b2cs", []))
    b2cs_total += sum(
        money(x.get("nil_amt"))
        for x in payload.get("nil", {}).get("inv", [])
    )

    supeco_total = sum(
        money(x.get("suppval")) for x in payload.get("supeco", {}).get("clttx", [])
    )

    if mode == CLEAN_PORTAL and abs(b2cs_total - supeco_total) > Decimal("0.01"):
        errors.append(
            f"B2CS taxable {b2cs_total} does not match SUPECO taxable {supeco_total}"
        )

    return errors


def gstr1_generation_report(
    payload: dict[str, Any],
    source_rows: list[dict[str, Any]],
    export_mode: str = CLEAN_PORTAL,
) -> dict[str, Any]:
    mode = normalize_export_mode(export_mode)
    period = str(payload.get("fp") or "")
    uploaded_platforms = sorted(
        {
            str(row.get("platform") or "unknown")
            for row in source_rows
            if row.get("platform")
        }
    )
    period_rows = [row for row in source_rows if row_belongs_to_period(row, period)]
    valid_rows = [row for row in period_rows if valid_for_b2cs(row)]
    exportable_rows = [row for row in period_rows if valid_for_export(row)]
    valid_by_platform = {
        platform: sum(1 for row in valid_rows if row.get("platform") == platform)
        for platform in uploaded_platforms
    }
    supeco_etins = [
        row.get("etin") for row in payload.get("supeco", {}).get("clttx", [])
    ]
    warnings = []
    if mode == GSTTOOL_COMPATIBLE and "flipkart" in uploaded_platforms:
        warnings.append("May differ for Flipkart due to report-cycle logic.")
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

    marketplace_totals: dict[str, dict[str, Any]] = {}
    for platform in uploaded_platforms:
        platform_rows = [
            row for row in exportable_rows if str(row.get("platform")) == platform
        ]
        marketplace_totals[platform] = {
            "rows": len(platform_rows),
            "taxable_value": json_amount(
                sum((money(row.get("taxable_value")) for row in platform_rows), Decimal("0.00"))
            ),
            "igst": json_amount(
                sum((money(row.get("igst")) for row in platform_rows), Decimal("0.00"))
            ),
            "cgst": json_amount(
                sum((money(row.get("cgst")) for row in platform_rows), Decimal("0.00"))
            ),
            "sgst": json_amount(
                sum((money(row.get("sgst")) for row in platform_rows), Decimal("0.00"))
            ),
            "cess": json_amount(
                sum((money(row.get("cess")) for row in platform_rows), Decimal("0.00"))
            ),
        }

    source_total = sum(
        (money(row.get("taxable_value")) for row in exportable_rows), Decimal("0.00")
    )
    output_total = sum(
        (money(row.get("txval")) for row in payload.get("b2cs", [])), Decimal("0.00")
    ) + sum(
        (money(row.get("nil_amt")) for row in payload.get("nil", {}).get("inv", [])),
        Decimal("0.00"),
    )
    if source_total != output_total:
        warnings.append(
            f"Source/output taxable reconciliation differs by {source_total - output_total}"
        )

    errors = validate_gstr1_schema(payload, mode)
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
        "marketplace_totals": marketplace_totals,
        "source_output_taxable_delta": json_amount(source_total - output_total),
        "period_filter": period_filter_debug(source_rows, period),
        "supeco_etins": supeco_etins,
        "warnings": warnings,
        "errors": errors,
    }


def period_filter_debug(
    source_rows: list[dict[str, Any]], period: str
) -> dict[str, Any]:
    debug: dict[str, Any] = {}
    for platform in sorted(
        {str(row.get("platform") or "unknown") for row in source_rows}
    ):
        platform_rows = [
            row
            for row in source_rows
            if str(row.get("platform") or "unknown") == platform
        ]
        included = [row for row in platform_rows if row_belongs_to_period(row, period)]
        excluded = [
            row for row in platform_rows if not row_belongs_to_period(row, period)
        ]
        debug[platform] = {
            "included": period_filter_bucket_debug(included),
            "excluded": period_filter_bucket_debug(excluded),
        }
    return debug


def period_filter_bucket_debug(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dated = [(document_date_value(row), row) for row in rows]
    dates = sorted(value for value, _ in dated if value is not None)

    def first_last(doc_type: str) -> dict[str, str | None]:
        values = sorted(
            {
                str(row.get("invoice_no") or "")
                for row in rows
                if str(row.get("doc_type") or "").lower() == doc_type
                and row.get("invoice_no")
            },
            key=document_sort_key,
        )
        return {
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
        }

    return {
        "rows": len(rows),
        "date_from": dates[0].isoformat() if dates else None,
        "date_to": dates[-1].isoformat() if dates else None,
        "invoice_no": first_last("invoice"),
        "credit_note_no": first_last("credit_note"),
        "debit_note_no": first_last("debit_note"),
    }


def build_gstr1_json(
    gstin: str,
    period: str,
    rows: list[dict],
    export_mode: str = CLEAN_PORTAL,
) -> dict:
    mode = normalize_export_mode(export_mode)
    valid_rows = [row for row in rows if row_belongs_to_period(row, period)]

    b2cs = build_b2cs(gstin, valid_rows, mode)
    nil_rows = build_nil(valid_rows)
    hsn_rows = build_hsn(valid_rows)
    supeco_rows = build_supeco(valid_rows, mode)

    b2cs_txval = sum(money(x.get("txval")) for x in b2cs) + sum(
        money(x.get("nil_amt")) for x in nil_rows
    )
    eco_txval = sum(money(x.get("suppval")) for x in supeco_rows)

    if mode == CLEAN_PORTAL and abs(b2cs_txval - eco_txval) > Decimal("0.01"):
        raise ValueError(
            f"B2CS taxable {b2cs_txval} does not match SUPECO taxable {eco_txval}"
        )

    payload = {
        "gstin": gstin,
        "fp": period,
        "version": GST_VERSION,
        "hash": "hash",
        "b2cs": b2cs,
        "supeco": {"clttx": supeco_rows},
        "doc_issue": build_doc_issue(valid_rows, mode),
    }
    if nil_rows:
        payload["nil"] = {"inv": nil_rows}
    if hsn_rows:
        payload["hsn"] = hsn_rows
    return payload
