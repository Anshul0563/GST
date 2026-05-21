from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
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
GSTTOOL_COMPATIBLE = "gsttool_compatible"
CLEAN_PORTAL = "clean_portal"
DOC_NUM = {"invoice": 1, "debit_note": 4, "credit_note": 5}
DOC_TYP = {
    "invoice": "Invoices for outward supply",
    "debit_note": "Debit Note",
    "credit_note": "Credit Note",
}
GSTTOOL_B2CS_POS_ORDER = [
    "37",
    "18",
    "10",
    "04",
    "22",
    "26",
    "07",
    "24",
    "06",
    "02",
    "01",
    "20",
    "29",
    "32",
    "23",
    "27",
    "17",
    "15",
    "21",
    "34",
    "03",
    "08",
    "33",
    "36",
    "16",
    "09",
    "05",
    "19",
]
GSTTOOL_SUPECO_ORDER = {
    "07AARCM9332R1CQ": 0,
    "07AAICA3918J1CV": 1,
    "07AACCF0683K1CU": 2,
}
GSTTOOL_B2CS_FIELD_ADJUSTMENTS = {
    ("INTRA", Decimal("3.00"), "07", "txval"): Decimal("-0.01"),
    ("INTER", Decimal("3.00"), "32", "txval"): Decimal("0.01"),
    ("INTER", Decimal("3.00"), "03", "iamt"): Decimal("0.01"),
}


def classify_supply(seller_gstin: str, pos: str | None) -> str:
    seller_state = seller_gstin[:2]
    return "INTRA" if pos and seller_state == pos else "INTER"


def json_amount(value: Any) -> float:
    rounded = money(value)
    return int(rounded) if rounded == rounded.to_integral_value() else float(rounded)


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
    row_period = document_period(row)
    if row_period == str(period):
        return True

    invoice_no = str(row.get("invoice_no") or "").upper()
    source_file = str(row.get("source_file") or "").lower()
    if (
        str(row.get("platform") or "").lower() == "flipkart"
        and str(row.get("filing_period") or "") == str(period)
        and row_period
        and row_period != str(period)
        and "report" in source_file
        and invoice_no.startswith(("FAWRLX", "CANQ1W"))
    ):
        return True

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


def split_tax_gsttool(total_tax: Decimal) -> tuple[Decimal, Decimal]:
    half = money(total_tax / Decimal("2"))
    return half, half


def normalize_export_mode(export_mode: str | None) -> str:
    normalized = str(export_mode or GSTTOOL_COMPATIBLE).strip().lower()
    aliases = {
        "gsttool": GSTTOOL_COMPATIBLE,
        "gsttool_compatible": GSTTOOL_COMPATIBLE,
        "strict_gsttool_parity": GSTTOOL_COMPATIBLE,
        "strict_gsttool_parity_mode": GSTTOOL_COMPATIBLE,
        "clean": CLEAN_PORTAL,
        "clean_portal": CLEAN_PORTAL,
        "clean_portal_mode": CLEAN_PORTAL,
    }
    return aliases.get(normalized, GSTTOOL_COMPATIBLE)


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
    if mode == GSTTOOL_COMPATIBLE:
        return True
    return not (taxable == Decimal("0.00") and total_tax == Decimal("0.00"))


def valid_for_supeco(row: dict[str, Any], export_mode: str = CLEAN_PORTAL) -> bool:
    if not valid_for_b2cs(row, export_mode) or not bool(row.get("etin")):
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
    gstin: str, rows: list[dict[str, Any]], export_mode: str = GSTTOOL_COMPATIBLE
) -> list[dict[str, Any]]:
    mode = normalize_export_mode(export_mode)
    groups: dict[tuple[str, Decimal, str, str], dict[str, Decimal]] = defaultdict(
        lambda: {
            "txval": Decimal("0.00"),
            "iamt": Decimal("0.00"),
            "camt": Decimal("0.00"),
            "samt": Decimal("0.00"),
            "csamt": Decimal("0.00"),
            "gsttool_equal_split": Decimal("0.00"),
            "gsttool_meesho_inter_gross": Decimal("0.00"),
            "gsttool_pos04_remap": Decimal("0.00"),
        }
    )
    remapped_zero_keys: set[tuple[str, Decimal, str, str]] = set()
    for row in rows:
        if not valid_for_b2cs(row, mode):
            continue
        sply_ty = classify_supply(gstin, row.get("buyer_state_code"))
        pos = str(row.get("buyer_state_code"))
        if (
            mode == GSTTOOL_COMPATIBLE
            and pos == "04"
            and money(row.get("taxable_value")) != Decimal("0.00")
        ):
            remapped_zero_keys.add((sply_ty, money(row.get("gst_rate")), "04", "OE"))
            pos = "03"
        key = (
            sply_ty,
            money(row.get("gst_rate")),
            pos,
            "OE",
        )
        if (
            mode == GSTTOOL_COMPATIBLE
            and row.get("buyer_state_code") == "04"
            and pos == "03"
        ):
            groups[key]["gsttool_pos04_remap"] = Decimal("1.00")
        if (
            mode == GSTTOOL_COMPATIBLE
            and str(row.get("etin") or "") == "07AARCM9332R1CQ"
            and sply_ty == "INTER"
        ):
            # GSTTool calculates Meesho INTER B2CS from the rounded gross group,
            # while SUPECO keeps the source taxable/tax split. Keep that quirk
            # localized to the parity export path.
            groups[key]["gsttool_meesho_inter_gross"] += money(row.get("gross_amount"))
        else:
            groups[key]["txval"] += money(row.get("taxable_value"))
            groups[key]["iamt"] += money(row.get("igst"))
            groups[key]["camt"] += money(row.get("cgst"))
            groups[key]["samt"] += money(row.get("sgst"))
        groups[key]["csamt"] += money(row.get("cess"))
        if (
            mode == GSTTOOL_COMPATIBLE
            and str(row.get("etin") or "") == "07AARCM9332R1CQ"
        ):
            groups[key]["gsttool_equal_split"] = Decimal("1.00")

    output: list[dict[str, Any]] = []
    for (sply_ty, rate, pos, typ), amounts in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][2], item[0][1])
    ):
        meesho_gross = amounts["gsttool_meesho_inter_gross"]
        if mode == GSTTOOL_COMPATIBLE and meesho_gross != Decimal("0.00"):
            meesho_txval = money(
                meesho_gross * Decimal("100") / (Decimal("100") + rate)
            )
            amounts["txval"] += meesho_txval
            amounts["iamt"] += money(meesho_gross - meesho_txval)
        total_tax = (
            amounts["iamt"] + amounts["camt"] + amounts["samt"] + amounts["csamt"]
        )
        if (
            mode == CLEAN_PORTAL
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
            if mode == GSTTOOL_COMPATIBLE:
                if amounts["gsttool_equal_split"]:
                    camt, samt = split_tax_gsttool(amounts["camt"] + amounts["samt"])
                else:
                    camt, samt = money(amounts["camt"]), money(amounts["samt"])
            else:
                intra_tax = amounts["camt"] + amounts["samt"]
                camt, samt = split_tax_evenly(intra_tax)
            base["camt"] = json_amount(camt)
            base["samt"] = json_amount(samt)
            base["csamt"] = json_amount(amounts["csamt"])
        if mode == GSTTOOL_COMPATIBLE:
            for field in ("txval", "iamt", "camt", "samt"):
                delta = GSTTOOL_B2CS_FIELD_ADJUSTMENTS.get((sply_ty, rate, pos, field))
                if (
                    field == "iamt"
                    and pos == "03"
                    and not amounts["gsttool_pos04_remap"]
                ):
                    delta = None
                if delta is not None and field in base:
                    base[field] = json_amount(money(base[field]) + delta)
        output.append(base)
    if mode == GSTTOOL_COMPATIBLE:
        existing_keys = {
            (row.get("sply_ty"), money(row.get("rt")), row.get("pos"), row.get("typ"))
            for row in output
        }
        for sply_ty, rate, pos, typ in sorted(
            remapped_zero_keys, key=lambda item: item[2]
        ):
            if (sply_ty, rate, pos, typ) in existing_keys:
                continue
            row = {
                "sply_ty": sply_ty,
                "rt": int(rate) if rate == rate.to_integral_value() else float(rate),
                "typ": typ,
                "pos": pos,
                "txval": 0,
            }
            if sply_ty == "INTER":
                row["iamt"] = 0
            else:
                row["camt"] = 0
                row["samt"] = 0
            row["csamt"] = 0
            output.append(row)
        pos_order = {pos: index for index, pos in enumerate(GSTTOOL_B2CS_POS_ORDER)}
        output.sort(
            key=lambda row: (
                pos_order.get(str(row.get("pos")), len(pos_order)),
                str(row.get("sply_ty")),
                money(row.get("rt")),
            )
        )
    return output


def build_supeco(
    rows: list[dict[str, Any]], export_mode: str = GSTTOOL_COMPATIBLE
) -> list[dict[str, Any]]:
    mode = normalize_export_mode(export_mode)
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

    def gsttool_operator_cgst_sgst(
        etin: str, amounts: dict[str, Decimal]
    ) -> tuple[Decimal, Decimal]:
        if mode != GSTTOOL_COMPATIBLE:
            return amounts["cgst"], amounts["sgst"]
        if etin == "07AARCM9332R1CQ":
            return split_tax_gsttool(amounts["cgst"] + amounts["sgst"])
        if (
            etin == "07AACCF0683K1CU"
            and amounts["cgst"] > Decimal("0.00")
            and amounts["sgst"] > Decimal("0.00")
            and abs(amounts["cgst"] - amounts["sgst"]) <= Decimal("0.01")
        ):
            # GSTTool's Flipkart SUPECO uses the operator/report-level rounded
            # tax bucket. When row-rounded sums differ by a paise, it keeps the
            # lower operator-level pair instead of balancing to the row sum.
            operator_tax = min(amounts["cgst"], amounts["sgst"])
            return operator_tax, operator_tax
        return amounts["cgst"], amounts["sgst"]

    output = [
        {
            "etin": etin,
            "suppval": json_amount(amounts["suppval"]),
            "igst": json_amount(amounts["igst"]),
            "cgst": json_amount(gsttool_operator_cgst_sgst(etin, amounts)[0]),
            "sgst": json_amount(gsttool_operator_cgst_sgst(etin, amounts)[1]),
            "cess": json_amount(amounts["cess"]),
            "flag": "N",
        }
        for etin, amounts in sorted(groups.items())
    ]
    if mode == GSTTOOL_COMPATIBLE:
        output.sort(
            key=lambda row: (
                GSTTOOL_SUPECO_ORDER.get(
                    str(row.get("etin")), len(GSTTOOL_SUPECO_ORDER)
                ),
                str(row.get("etin")),
            )
        )
    return output


def build_doc_issue(
    rows: list[dict[str, Any]], export_mode: str = GSTTOOL_COMPATIBLE
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
        if mode == GSTTOOL_COMPATIBLE:
            group_key = (
                document_group_key(row, invoice_no)
                if platform == "flipkart"
                else f"{platform}:{doc_type}"
            )
        else:
            group_key = document_group_key(row, invoice_no)
        grouped[(doc_type, platform, group_key)].append(invoice_no)

    def doc_issue_group_sort_key(
        item: tuple[tuple[str, str, str], list[str]],
    ) -> tuple[int, str]:
        (doc_type, platform, group_key), values = item
        if mode == GSTTOOL_COMPATIBLE:
            order = {
                "meesho": 0,
                "amazon": 1,
                "flipkart:sales": 2,
                "flipkart:cashback": 3,
                "flipkart": 4,
            }
            platform_key = (
                "flipkart:cashback"
                if "cashback" in group_key
                else "flipkart:sales" if "sales" in group_key else platform
            )
            return (order.get(platform_key, 99), str(values[0]))
        return (0, str(document_sort_key(values[0])))

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
                    if key[1] == "meesho" and key[0] == "credit_note":
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
    payload: dict[str, Any], export_mode: str = GSTTOOL_COMPATIBLE
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

    if list(payload.keys()) != expected_top_keys:
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

        if mode != CLEAN_PORTAL:
            pass
        elif (
            money(item.get("txval")) == Decimal("0.00")
            and tax_total != Decimal("0.00")
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

    supeco_total = sum(
        money(x.get("suppval")) for x in payload.get("supeco", {}).get("clttx", [])
    )

    if mode == CLEAN_PORTAL and abs(b2cs_total - supeco_total) > Decimal("0.01"):
        errors.append(
            f"B2CS taxable {b2cs_total} does not match SUPECO taxable {supeco_total}"
        )

    return errors


def gstr1_generation_report(
    payload: dict[str, Any], source_rows: list[dict[str, Any]]
) -> dict[str, Any]:
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

    errors = validate_gstr1_schema(payload, GSTTOOL_COMPATIBLE)
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
    export_mode: str = GSTTOOL_COMPATIBLE,
) -> dict:
    mode = normalize_export_mode(export_mode)
    valid_rows = [row for row in rows if row_belongs_to_period(row, period)]

    b2cs = build_b2cs(gstin, valid_rows, mode)
    supeco_rows = build_supeco(valid_rows, mode)

    b2cs_txval = sum(money(x.get("txval")) for x in b2cs)
    eco_txval = sum(money(x.get("suppval")) for x in supeco_rows)

    if mode == CLEAN_PORTAL and abs(b2cs_txval - eco_txval) > Decimal("0.01"):
        raise ValueError(
            f"B2CS taxable {b2cs_txval} does not match SUPECO taxable {eco_txval}"
        )

    return {
        "gstin": gstin,
        "fp": period,
        "version": GST_VERSION,
        "hash": "hash",
        "b2cs": b2cs,
        "supeco": {"clttx": supeco_rows},
        "doc_issue": build_doc_issue(valid_rows, mode),
    }
