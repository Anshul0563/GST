from pathlib import Path
from decimal import Decimal

import pandas as pd

from app.parsers.flipkart import FlipkartParser


GSTIN = "07TCRPS8655B1ZK"


def test_flipkart_sales_report_uses_final_invoice_amount(tmp_path: Path):
    source = tmp_path / "flipkart.xlsx"
    pd.DataFrame(
        [
            {
                "Seller GSTIN": GSTIN,
                "Order ID": "OD-1",
                "Order Item ID": "ITEM-1",
                "Event Type": "Sale",
                "Order Date": "2026-07-06",
                "Item Quantity": 1,
                "Price before discount": 98,
                "Final Invoice Amount (Price after discount+Shipping Charges)": 91,
                "Taxable Value (Final Invoice Amount -Taxes)": 88.35,
                "IGST Rate": 3,
                "IGST Amount": 2.65,
                "Buyer Invoice ID": "LWABOG7270000043",
                "Buyer Invoice Date": "2026-07-07",
                "Customer's Delivery State": "Kerala",
            }
        ]
    ).to_excel(source, sheet_name="Sales Report", index=False)

    result = FlipkartParser(GSTIN, "072026").parse([source])

    assert result.errors == []
    assert len(result.transactions) == 1
    assert result.transactions[0]["gross_amount"] == 91


def test_reference_flipkart_report_parses_when_available():
    source = Path(
        "/home/jarvis/Downloads/ff855857-f7c1-4ee3-9d82-728b5a332f30_1786432092000.xlsx"
    )
    if not source.exists():
        return

    result = FlipkartParser(GSTIN, "072026").parse([source])

    assert result.errors == []
    assert len(result.transactions) == 48
    assert result.transactions[0]["gross_amount"] == 91


def test_flipkart_cashback_report_preserves_source_tax_signs(tmp_path: Path):
    source = tmp_path / "flipkart.xlsx"
    pd.DataFrame(
        [
            {
                "Seller GSTIN": GSTIN,
                "Order ID": "OD-CB-1",
                "Order Item ID": "ITEM-CB-1",
                "Document Type": "Credit Note",
                "Document Sub Type": "Sale",
                "Credit Note ID/ Debit Note ID": "LYAA9U7270000001",
                "Invoice Amount": 5.28,
                "Invoice Date": "2026-07-10",
                "Taxable Value": 5.13,
                "IGST Rate": 3,
                "IGST Amount": 0.15,
            },
            {
                "Seller GSTIN": GSTIN,
                "Order ID": "OD-CB-2",
                "Order Item ID": "ITEM-CB-2",
                "Document Type": "Debit Note",
                "Document Sub Type": "Return",
                "Credit Note ID/ Debit Note ID": "LZAA9B7270000001",
                "Invoice Amount": -5.28,
                "Invoice Date": "2026-07-11",
                "Taxable Value": -5.13,
                "IGST Rate": 3,
                "IGST Amount": -0.15,
            },
        ]
    ).to_excel(source, sheet_name="Cash Back Report", index=False)

    result = FlipkartParser(GSTIN, "072026").parse([source])

    assert result.errors == []
    assert [row["taxable_value"] for row in result.transactions] == [
        Decimal("5.13"),
        Decimal("-5.13"),
    ]
    assert [row["igst"] for row in result.transactions] == [
        Decimal("0.15"),
        Decimal("-0.15"),
    ]
