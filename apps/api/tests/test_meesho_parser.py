from pathlib import Path
from decimal import Decimal

import pandas as pd

from app.parsers.meesho import MeeshoParser
from app.services.gst import build_gstr1_json


def test_meesho_credit_conversion_is_included_in_document_issue_metadata(tmp_path: Path):
    sales = tmp_path / "tcs_sales.xlsx"
    invoice = tmp_path / "Tax_invoice_details.xlsx"

    pd.DataFrame(
        [
            {
                "sub_order_num": "SO-CONVERSION",
                "order_date": "2026-07-01",
                "hsn_code": "711790",
                "quantity": 1,
                "gst_rate": 3,
                "total_taxable_sale_value": 100,
                "tax_amount": 3,
                "total_invoice_value": 103,
                "end_customer_state_new": "TELANGANA",
                "eco_tcs_gstin": "07AARCM9332R1CQ",
            }
        ]
    ).to_excel(sales, index=False)
    pd.DataFrame(
        [
            {
                "Type": "CREDIT_CONVERSION",
                "Order Date": "2026-07-01",
                "Suborder No.": "SO-CONVERSION",
                "Product Description": "Jewellery",
                "HSN": "711790",
                "Invoice No.": "6p5kc27CC6",
            }
        ]
    ).to_excel(invoice, sheet_name="Invoice_Info", index=False)

    result = MeeshoParser("07TCRPS8655B1ZK", "072026").parse([sales, invoice])

    assert result.errors == []
    assert any(
        row["doc_type"] == "credit_note"
        and row["invoice_no"] == "6p5kc27CC6"
        and row["etin"] == "07AARCM9332R1CQ"
        and row["validation_status"] == "skipped"
        for row in result.transactions
    )


def test_meesho_report_month_includes_prior_month_adjustment(tmp_path: Path):
    sales = tmp_path / "tcs_sales.xlsx"
    pd.DataFrame(
        [
            {
                "sub_order_num": "SO-AUG-ADJUSTMENT",
                "order_date": "2026-07-30",
                "financial_year": 2026,
                "month_number": 8,
                "hsn_code": "711790",
                "quantity": 0,
                "gst_rate": 3,
                "total_taxable_sale_value": -23,
                "tax_amount": -0.69,
                "total_invoice_value": -23.69,
                "end_customer_state_new": "UTTAR PRADESH",
                "eco_tcs_gstin": "07AARCM9332R1CQ",
            }
        ]
    ).to_excel(sales, index=False)

    result = MeeshoParser("07TCRPS8655B1ZK", "082026").parse([sales])

    assert result.errors == []
    assert len(result.transactions) == 1
    assert result.transactions[0]["invoice_date"].isoformat() == "2026-08-01"
    assert result.transactions[0]["taxable_value"] == -23


def test_meesho_period_and_etin_are_read_from_source(tmp_path: Path):
    sales = tmp_path / "tcs_sales.xlsx"
    pd.DataFrame(
        [
            {
                "sub_order_num": "SO-JAN-ADJUSTMENT",
                "order_date": "2026-12-31",
                "financial_year": 2027,
                "month_number": 1,
                "hsn_code": "711790",
                "quantity": 0,
                "gst_rate": 3,
                "total_taxable_sale_value": -10,
                "tax_amount": -0.30,
                "total_invoice_value": -10.30,
                "end_customer_state_new": "UTTAR PRADESH",
                "eco_tcs_gstin": "29AABCU9603R1ZV",
            }
        ]
    ).to_excel(sales, index=False)

    result = MeeshoParser("07TCRPS8655B1ZK", "012027").parse([sales])

    assert result.errors == []
    assert len(result.transactions) == 1
    assert result.transactions[0]["filing_period"] == "012027"
    assert result.transactions[0]["invoice_date"].isoformat() == "2027-01-01"
    assert result.transactions[0]["etin"] == "29AABCU9603R1ZV"


def test_real_meesho_august_reports_reconcile_when_available():
    sales = Path("/home/jarvis/Downloads/gst_3412749_8_2026/tcs_sales.xlsx")
    returns = Path("/home/jarvis/Downloads/gst_3412749_8_2026/tcs_sales_return.xlsx")
    invoice = Path(
        "/home/jarvis/Downloads/3412749_2026-08-01_2026-08-31_TAX_INVOICE/"
        "Tax_invoice_details.xlsx"
    )
    if not all(path.exists() for path in (sales, returns, invoice)):
        return

    result = MeeshoParser("07TCRPS8655B1ZK", "082026").parse(
        [sales, returns, invoice]
    )
    financial = [
        row
        for row in result.transactions
        if row["source_file"].startswith(("tcs_sales.xlsx", "tcs_sales_return.xlsx"))
    ]

    assert result.errors == []
    assert result.debug["meesho_financial_rows"] == 430
    assert result.debug["meesho_metadata_only_rows"] == 40
    assert result.debug["meesho_total_result_rows"] == 470
    assert sum(row["doc_type"] == "invoice" for row in financial) == 338
    assert sum(row["doc_type"] == "credit_note" for row in financial) == 92
    assert sum(row["buyer_state_code"] == "07" for row in financial if row["doc_type"] == "invoice") == 17
    assert sum(row["buyer_state_code"] == "07" for row in financial if row["doc_type"] == "credit_note") == 5

    payload = build_gstr1_json("07TCRPS8655B1ZK", "082026", result.transactions)
    assert sum(Decimal(str(row["txval"])) for row in payload["b2cs"]) == Decimal("33062.37")
    assert sum(
        Decimal(str(row.get("iamt", 0)))
        + Decimal(str(row.get("camt", 0)))
        + Decimal(str(row.get("samt", 0)))
        for row in payload["b2cs"]
    ) == Decimal("1025.18")
    assert payload["nil"]["inv"] == [
        {"sply_ty": "INTRB2B", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRAB2B", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRB2C", "nil_amt": 114.19, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRAB2C", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
    ]
    assert not any(row["rt"] == 0 for row in payload["b2cs"])
    assert len(payload["hsn"]["hsn_b2c"]) == 3
    assert payload["supeco"]["clttx"][0]["suppval"] == 33176.56
    assert result.debug["meesho_source_breakdown"]["sales"]["taxable_value"] == "48269.47"
    assert result.debug["meesho_source_breakdown"]["returns"]["taxable_value"] == "15092.91"
