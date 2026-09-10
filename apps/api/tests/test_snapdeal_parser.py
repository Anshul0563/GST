from decimal import Decimal
from pathlib import Path

import pandas as pd
from app.parsers.snapdeal import (
    REQUIRED_HEADERS,
    SHEET_5B,
    SHEET_7A,
    SHEET_7B,
    SHEET_12,
    SHEET_GSTR8,
    SHEET_SERIES,
    SnapdealParser,
)
from app.services.gst import build_gstr1_json

SELLER = "07ABCDE1234F1Z5"
SNAPDEAL = "07AAICA4872D1Z8"


def _frame(sheet: str, values: dict[str, object] | None = None) -> pd.DataFrame:
    headers = sorted(REQUIRED_HEADERS[sheet])
    return pd.DataFrame(
        [headers, [((values or {}).get(header, "")) for header in headers]]
    )


def _workbook_rows() -> dict[str, pd.DataFrame]:
    five_b = _frame(
        SHEET_5B,
        {
            "tcs gstin of snapdeal": SNAPDEAL,
            "gstin of seller": SELLER,
            "delivered state": "27",
            "invoice number": "SD-1001",
            "order invoice date": "15/08/2026",
            "invoice amount": "118.99",
            "igst %": "18",
            "taxable amount": "100.125",
            "igst amount": "18.99",
            "cess %": "0",
            "cess amount": "0.00",
        },
    )
    seven_a = _frame(
        SHEET_7A,
        {
            "tcs gstin of snapdeal": SNAPDEAL,
            "gstin of seller": SELLER,
            "gross taxable value": "200.00",
            "taxable sales return value": "-10.00",
            "aggregate taxable value": "190.00",
            "cgst %": "9",
            "cgst amount": "17.10",
            "sgst/ut %": "9",
            "sgst/ut amount": "17.10",
            "cess %": "0",
            "cess amount": "0.00",
        },
    )
    seven_b = _frame(
        SHEET_7B,
        {
            "tcs gstin of snapdeal": SNAPDEAL,
            "delivered state": "29",
            "gstin of seller": SELLER,
            "gross taxable value": "300.00",
            "taxable sales return value": "-25.00",
            "aggregate taxable value": "275.00",
            "igst %": "18",
            "igst amount": "49.50",
            "cess %": "0",
            "cess amount": "0.00",
        },
    )
    return {
        SHEET_5B: five_b,
        SHEET_7A: seven_a,
        SHEET_7B: seven_b,
        SHEET_12: _frame(
            SHEET_12,
            {
                "gstin of seller": SELLER,
                "hsn number": "9983",
                "total quantity": "2",
                "total value": "236.99",
                "total taxable value": "200.00",
                "igst amount": "18.99",
                "cgst amount": "17.10",
                "sgst amount": "17.10",
                "cess amount": "0.00",
            },
        ),
        SHEET_GSTR8: pd.DataFrame([["ignored gstr-8 data"]]),
        SHEET_SERIES: _frame(
            SHEET_SERIES,
            {
                "trx type": "B2C",
                "gstin": SELLER,
                "invoice series from": "SD-1001",
                "invoice series to": "SD-1001",
                "total number of invoices": "1",
                "cancelled if any": "0",
                "net invoice issued": "1",
            },
        ),
    }


def test_snapdeal_parser_uses_sheet_specific_mapping_and_source_tax(monkeypatch):
    workbook = _workbook_rows()
    monkeypatch.setattr(
        "app.parsers.snapdeal.raw_frames",
        lambda path: list(workbook.items()),
    )

    result = SnapdealParser(SELLER, "082026").parse([Path("snapdeal.xlsx")])

    assert result.errors == []
    assert len(result.transactions) == 3
    assert SHEET_GSTR8 in result.debug["ignored_sheets"]
    assert result.transactions[0]["taxable_value"] == Decimal("100.13")
    assert result.transactions[0]["igst"] == Decimal("18.99")
    assert result.transactions[1]["taxable_value"] == Decimal("190.00")
    assert result.transactions[1]["buyer_state_code"] == "07"
    assert result.transactions[2]["buyer_state_code"] == "29"
    assert result.debug["hsn_summary"][0]["hsn"] == "9983"
    assert result.debug["invoice_series"][0]["net"] == Decimal("1.00")

    payload = build_gstr1_json(SELLER, "082026", result.transactions)
    assert sum(Decimal(str(item["txval"])) for item in payload["b2cs"]) == Decimal(
        "565.13"
    )
    assert sum(
        Decimal(str(item.get("iamt", 0))) for item in payload["b2cs"]
    ) == Decimal("68.49")
    assert payload["doc_issue"]["doc_det"] == []


def test_snapdeal_parser_rejects_selected_profile_gstin_mismatch(monkeypatch):
    workbook = _workbook_rows()
    monkeypatch.setattr(
        "app.parsers.snapdeal.raw_frames",
        lambda path: list(workbook.items()),
    )

    result = SnapdealParser("27ABCDE1234F1Z5", "082026").parse([Path("snapdeal.xlsx")])

    assert result.transactions == []
    assert "GSTIN mismatch" in result.errors[0]["error"]


def test_snapdeal_parser_rejects_missing_required_sheet(monkeypatch):
    workbook = _workbook_rows()
    del workbook[SHEET_7B]
    monkeypatch.setattr(
        "app.parsers.snapdeal.raw_frames",
        lambda path: list(workbook.items()),
    )

    result = SnapdealParser(SELLER, "082026").parse([Path("snapdeal.xlsx")])

    assert "missing sheet" in result.errors[0]["error"]


def test_real_snapdeal_report_has_expected_structure_when_available():
    path = Path("/home/jarvis/Downloads/Sc8f1c_AUG_2026_92415421_432337.xlsx")
    if not path.exists():
        return

    result = SnapdealParser(SELLER, "082026").parse([path])

    assert result.errors == []
    assert result.transactions == []
    assert SHEET_GSTR8 in result.debug["ignored_sheets"]
