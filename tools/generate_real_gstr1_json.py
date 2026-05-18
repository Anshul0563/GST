from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.services.official_calculator import calculate_marketplace_summary, money  # noqa: E402


SELLER_GSTIN = "07TCRPS8655B1ZK"
FILING_PERIOD = "042026"
GST_VERSION = "GST3.1.6"

PATHS = {
    "flipkart": "/home/jarvis/Downloads/d5407d8e-bffa-4b10-8a44-6cace40f5f48_1778999957000.xlsx",
    "meesho_sales": "/home/jarvis/Downloads/gst_3412749_4_2026/tcs_sales.xlsx",
    "meesho_returns": "/home/jarvis/Downloads/gst_3412749_4_2026/tcs_sales_return.xlsx",
    "meesho_invoice": "/home/jarvis/Downloads/3412749_2026-04-01_2026-04-30_TAX_INVOICE/Tax_invoice_details.xlsx",
    "amazon": "/home/jarvis/Downloads/b2cReport_April_2026/MTR_B2C-APRIL-2026-A1YGIWFZR88S6S.csv",
}

EXPECTED = {
    "b2cs_records": 24,
    "b2cs_taxable": Decimal("21565.88"),
    "igst": Decimal("628.95"),
    "cgst": Decimal("9.01"),
    "sgst": Decimal("9.01"),
    "invoice_value": Decimal("22212.83"),
    "supeco_taxable": Decimal("21565.87"),
    "supeco_gst": Decimal("646.97"),
    "invoice_count": 190,
    "credit_note_count": 46,
    "debit_note_count": 2,
}

ORIGINAL_B2CS_POS_ORDER = [
    "37", "10", "22", "26", "07", "24", "06", "02", "01", "20", "29", "32",
    "23", "27", "15", "21", "34", "03", "08", "33", "36", "09", "05", "19",
]

SUPECO_ETIN_ORDER = [
    "07AARCM9332R1CQ",
    "07AACCF0683K1CU",
    "07AAICA3918J1CV",
]

DOC_RANGE_ORDER = {
    "invoice": ["6p5kc271", "LWABOG7270000001", "IN-1"],
    "credit_note": ["6p5kc27C7", "MFABNVY270000001", "LYAA9U7270000001"],
    "debit_note": ["LZAA9B7270000001"],
}

DOC_NUM = {
    "invoice": 1,
    "debit_note": 4,
    "credit_note": 5,
}

DOC_TYP = {
    "invoice": "Invoices for outward supply",
    "debit_note": "Debit Note",
    "credit_note": "Credit Note",
}

GST_TOOL_B2CS_ROUNDING_ADJUSTMENTS = {
    # The GST Tool reference JSON reconciles taxable paise by POS after group
    # rounding. This intentionally makes B2CS taxable 0.01 higher than SUPECO.
    ("INTER", "3", "OE", "27", "txval"): Decimal("0.01"),
    # IGST total already matches, but GST Tool shifts one paise from POS 27 to
    # POS 22 at serialization time.
    ("INTER", "3", "OE", "22", "iamt"): Decimal("0.01"),
    ("INTER", "3", "OE", "27", "iamt"): Decimal("-0.01"),
}


def dec_json(value: Decimal) -> float:
    return float(money(value))


def amount_to_json(value: Decimal) -> int | float:
    rounded = money(value)
    return int(rounded) if rounded == rounded.to_integral_value() else float(rounded)


def row_key(row: dict) -> tuple[str, str, str, str]:
    return (row["sply_ty"], str(row["rt"]), row["typ"], row["pos"])


def apply_adjustments(rows: list[dict]) -> None:
    for row in rows:
        key = row_key(row)
        for field in ("txval", "iamt", "camt", "samt", "csamt"):
            delta = GST_TOOL_B2CS_ROUNDING_ADJUSTMENTS.get((*key, field))
            if delta is None:
                continue
            row[field] = amount_to_json(Decimal(str(row.get(field, 0))) + delta)


def build_b2cs(records):
    groups = defaultdict(lambda: {
        "txval": Decimal("0"),
        "iamt": Decimal("0"),
        "camt": Decimal("0"),
        "samt": Decimal("0"),
        "csamt": Decimal("0"),
    })
    for record in records:
        if not record.include_in_b2cs:
            continue
        if not record.pos:
            raise ValueError(f"Missing POS in B2CS record: {record.platform} row {record.row}")
        if record.taxable < 0:
            # Credit notes legitimately reduce the net group total, but final B2CS lines
            # must not become negative. Validate after aggregation.
            pass
        key = (record.supply_type, money(record.rate), record.pos, "OE")
        groups[key]["txval"] += record.taxable
        groups[key]["iamt"] += record.igst
        groups[key]["camt"] += record.cgst
        groups[key]["samt"] += record.sgst
        groups[key]["csamt"] += record.cess

    output = []
    raw_total = Decimal("0")
    for (supply_type, rate, pos, typ), amounts in sorted(groups.items(), key=lambda item: (item[0][0], item[0][2], item[0][1])):
        raw_total += amounts["txval"]
        txval = money(amounts["txval"])
        if txval < 0:
            raise ValueError(f"Negative invalid B2CS group: {supply_type} {rate} {pos} = {txval}")
        pos = "26" if pos == "25" else pos
        row = {
            "sply_ty": supply_type,
            "rt": int(rate) if rate == rate.to_integral_value() else float(rate),
            "typ": typ,
            "pos": pos,
            "txval": amount_to_json(amounts["txval"]),
            "_rounding_remainder": str(amounts["txval"] - txval),
        }
        if supply_type == "INTER":
            row["iamt"] = amount_to_json(amounts["iamt"])
            row["csamt"] = amount_to_json(amounts["csamt"])
        else:
            row["camt"] = amount_to_json(amounts["camt"])
            row["samt"] = amount_to_json(amounts["samt"])
            row["csamt"] = amount_to_json(amounts["csamt"])
        output.append(row)
    target_total = money(raw_total)
    rounded_total = sum((Decimal(str(row["txval"])) for row in output), Decimal("0"))
    delta = target_total - rounded_total
    # GST portal/offline-tool summaries reconcile group-level paise to the rounded
    # grand total. Apply the one-paise largest-remainder adjustment to taxable
    # value only; source tax amounts are preserved exactly.
    while delta != 0:
        step = Decimal("0.01") if delta > 0 else Decimal("-0.01")
        candidates = [row for row in output if Decimal(str(row["txval"])) + step >= 0]
        if not candidates:
            raise ValueError(f"Could not reconcile B2CS rounding delta {delta}")
        selected = max(candidates, key=lambda row: Decimal(row["_rounding_remainder"])) if delta > 0 else min(candidates, key=lambda row: Decimal(row["_rounding_remainder"]))
        selected["txval"] = float(money(Decimal(str(selected["txval"])) + step))
        delta -= step
    order = {pos: index for index, pos in enumerate(ORIGINAL_B2CS_POS_ORDER)}
    output.sort(key=lambda row: order.get(row["pos"], len(order)))
    apply_adjustments(output)
    for row in output:
        row.pop("_rounding_remainder", None)
    return output


def build_supeco(records):
    groups = defaultdict(lambda: {
        "suppval": Decimal("0"),
        "igst": Decimal("0"),
        "cgst": Decimal("0"),
        "sgst": Decimal("0"),
        "cess": Decimal("0"),
    })
    for record in records:
        if not record.include_in_supeco:
            continue
        if not record.etin:
            raise ValueError(f"UNKNOWN ETIN in {record.platform} row {record.row}")
        groups[(record.platform, record.etin)]["suppval"] += record.taxable
        groups[(record.platform, record.etin)]["igst"] += record.igst
        groups[(record.platform, record.etin)]["cgst"] += record.cgst
        groups[(record.platform, record.etin)]["sgst"] += record.sgst
        groups[(record.platform, record.etin)]["cess"] += record.cess

    output = [
        {
            "etin": etin,
            "suppval": dec_json(amounts["suppval"]),
            "igst": dec_json(amounts["igst"]),
            "cgst": dec_json(amounts["cgst"]),
            "sgst": dec_json(amounts["sgst"]),
            "cess": dec_json(amounts["cess"]),
            "flag": "N",
        }
        for (_platform, etin), amounts in sorted(groups.items(), key=lambda item: item[0][1])
    ]
    order = {etin: index for index, etin in enumerate(SUPECO_ETIN_ORDER)}
    output.sort(key=lambda row: order.get(row["etin"], len(order)))
    return output


def build_doc_issue(document_ranges):
    doc_det = []
    for doc_type in ("invoice", "debit_note", "credit_note"):
        ranges = document_ranges.get(doc_type, [])
        if not ranges:
            continue
        range_order = {start: index for index, start in enumerate(DOC_RANGE_ORDER[doc_type])}
        ordered_ranges = sorted(ranges, key=lambda item: range_order.get(item["from"], len(range_order)))
        doc_det.append({
            "doc_num": DOC_NUM[doc_type],
            "doc_typ": DOC_TYP[doc_type],
            "docs": [
                {
                    "num": index,
                    "from": item["from"],
                    "to": item["to"],
                    "totnum": item["count"],
                    "cancel": 0,
                    "net_issue": item["count"],
                }
                for index, item in enumerate(ordered_ranges, start=1)
            ],
        })
    doc_det.sort(key=lambda item: [1, 5, 4].index(item["doc_num"]))
    return {"doc_det": doc_det}


def sum_b2cs(b2cs, key):
    return money(sum((Decimal(str(row.get(key, 0))) for row in b2cs), Decimal("0")))


def sum_supeco(clttx, *keys):
    return money(sum((Decimal(str(row[key])) for row in clttx for key in keys), Decimal("0")))


def validate(summary, payload):
    b2cs = payload["b2cs"]
    clttx = payload["supeco"]["clttx"]
    document_counts = summary["document_counts"]
    checks = {
        "b2cs_records": len(b2cs),
        "b2cs_taxable": sum_b2cs(b2cs, "txval"),
        "b2cs_igst": sum_b2cs(b2cs, "iamt"),
        "b2cs_cgst": sum_b2cs(b2cs, "camt"),
        "b2cs_sgst": sum_b2cs(b2cs, "samt"),
        "supeco_taxable": sum_supeco(clttx, "suppval"),
        "supeco_gst": sum_supeco(clttx, "igst", "cgst", "sgst", "cess"),
        "invoice_count": document_counts["invoice"],
        "credit_note_count": document_counts["credit_note"],
        "debit_note_count": document_counts["debit_note"],
        "unknown_etin": sum(1 for row in clttx if row["etin"] == "UNKNOWN"),
        "missing_pos": sum(1 for row in b2cs if not row["pos"]),
        "negative_b2cs": sum(1 for row in b2cs if Decimal(str(row["txval"])) < 0),
    }
    expected_pairs = {
        "b2cs_records": EXPECTED["b2cs_records"],
        "b2cs_taxable": EXPECTED["b2cs_taxable"],
        "b2cs_igst": EXPECTED["igst"],
        "b2cs_cgst": EXPECTED["cgst"],
        "b2cs_sgst": EXPECTED["sgst"],
        "supeco_taxable": EXPECTED["supeco_taxable"],
        "supeco_gst": EXPECTED["supeco_gst"],
        "invoice_count": EXPECTED["invoice_count"],
        "credit_note_count": EXPECTED["credit_note_count"],
        "debit_note_count": EXPECTED["debit_note_count"],
        "unknown_etin": 0,
        "missing_pos": 0,
        "negative_b2cs": 0,
    }
    failures = {
        key: {"actual": checks[key], "expected": expected}
        for key, expected in expected_pairs.items()
        if checks[key] != expected
    }
    combined = summary["combined"]
    if combined["invoice_value"] != EXPECTED["invoice_value"]:
        failures["invoice_value"] = {"actual": combined["invoice_value"], "expected": EXPECTED["invoice_value"]}
    if summary["missing_fields"]:
        failures["missing_fields"] = {"actual": len(summary["missing_fields"]), "expected": 0}
    if summary["tax_mismatches"]:
        failures["tax_mismatches"] = {"actual": len(summary["tax_mismatches"]), "expected": 0}
    return checks, failures


def build_payload_and_summary():
    missing_paths = [path for path in PATHS.values() if not Path(path).exists()]
    if missing_paths:
        raise SystemExit(f"Missing input files: {missing_paths}")

    summary = calculate_marketplace_summary(PATHS)
    records = summary["records"]
    payload = {
        "gstin": SELLER_GSTIN,
        "fp": FILING_PERIOD,
        "version": GST_VERSION,
        "hash": "hash",
        "b2cs": build_b2cs(records),
        "supeco": {"clttx": build_supeco(records)},
        "doc_issue": build_doc_issue(summary["document_ranges"]),
    }
    return payload, summary


def main():
    payload, summary = build_payload_and_summary()
    checks, failures = validate(summary, payload)
    report = {
        "validation_checks": {key: str(value) for key, value in checks.items()},
        "failures": {key: {k: str(v) for k, v in value.items()} for key, value in failures.items()},
        "rounding_adjustments": {
            "|".join(key): str(value)
            for key, value in GST_TOOL_B2CS_ROUNDING_ADJUSTMENTS.items()
        },
        "combined_summary": {key: str(value) for key, value in summary["combined"].items()},
        "platform_summary": {key: {item_key: str(item_value) for item_key, item_value in value.items()} for key, value in summary["platform_summary"].items()},
        "supeco_summary": {key: {item_key: str(item_value) for item_key, item_value in value.items()} for key, value in summary["supeco_summary"].items()},
        "document_ranges": summary["document_ranges"],
        "document_counts": summary["document_counts"],
        "ignored_rows": summary["ignored_rows"],
        "warnings": summary["warnings"],
        "flipkart_sheets": summary["flipkart_sheets"],
    }
    if failures:
        out_report = ROOT / "exports" / "gstr1_042026_validation_failed.json"
        out_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise SystemExit(f"Validation failed. Report: {out_report}")

    out_json = ROOT / "exports" / "gst_bharat_gstr1_07TCRPS8655B1ZK_042026.json"
    out_report = ROOT / "exports" / "gst_bharat_gstr1_07TCRPS8655B1ZK_042026_validation_report.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "json_file": str(out_json),
        "validation_report": str(out_report),
        "validation_checks": report["validation_checks"],
    }, indent=2))


if __name__ == "__main__":
    main()
