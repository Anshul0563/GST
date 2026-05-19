import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.parsers.amazon import AmazonParser
from app.services.gst import build_gstr1_json
from app.services.official_calculator import calculate_marketplace_summary
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money


class GstCalculationTests(unittest.TestCase):
    def test_amazon_mtr_fraction_rate_and_iso_dates_parse_correctly(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "amazon.csv"
            path.write_text(
                '"Seller Gstin","Invoice Number","Invoice Date","Transaction Type","Order Id","Shipment Item Id","Quantity","Item Description","Hsn/sac","Sku","Ship To State","Invoice Amount","Tax Exclusive Gross","Igst Rate","Igst Tax","Tcs Igst Amount"\n'
                '07TCRPS8655B1ZK,IN-5,"2026-03-08 00:07:35",Shipment,406-0120907-7622716,556012092046,1,"Jhumka Earrings",7117,SKU-1,ODISHA,209,202.91,0.03,6.09,1.01\n'
            )
            result = AmazonParser("07TCRPS8655B1ZK", "032026").parse([path])

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.transactions), 1)
        txn = result.transactions[0]
        self.assertEqual(str(txn["invoice_date"]), "2026-03-08")
        self.assertEqual(txn["buyer_state_code"], "21")
        self.assertEqual(txn["gst_rate"], Decimal("3.00"))
        self.assertEqual(txn["igst"], Decimal("6.09"))
        self.assertEqual(txn["validation_status"], "valid")

    def test_inter_state_invoice_uses_igst(self):
        txn = finalize_transaction({
            "platform": "meesho",
            "gstin": "07ABCDE1234F1Z5",
            "etin": "07AARCM9332R1CQ",
            "filing_period": "042026",
            "invoice_no": "A1",
            "invoice_date": "2026-04-01",
            "doc_type": "invoice",
            "buyer_state_code": "37",
            "taxable_value": 1000,
            "gst_rate": 3,
            "igst": 30,
            "cgst": 0,
            "sgst": 0,
            "cess": 0,
        })
        self.assertEqual(txn["igst"], Decimal("30.00"))
        self.assertEqual(txn["cgst"], Decimal("0.00"))
        self.assertEqual(txn["sgst"], Decimal("0.00"))
        self.assertEqual(txn["validation_status"], "valid")

    def test_intra_state_invoice_splits_tax_even_if_source_has_igst(self):
        txn = finalize_transaction({
            "platform": "amazon",
            "gstin": "07ABCDE1234F1Z5",
            "etin": "29AAICA3918J1C9",
            "filing_period": "042026",
            "invoice_no": "A2",
            "invoice_date": "2026-04-01",
            "doc_type": "invoice",
            "buyer_state_code": "07",
            "taxable_value": 1000,
            "gst_rate": 18,
            "igst": 180,
            "cgst": 0,
            "sgst": 0,
            "cess": 0,
        })
        self.assertEqual(txn["igst"], Decimal("0.00"))
        self.assertEqual(txn["cgst"], Decimal("90.00"))
        self.assertEqual(txn["sgst"], Decimal("90.00"))
        self.assertEqual(txn["validation_status"], "valid")

    def test_credit_note_signs_are_normalized_before_validation(self):
        txn = finalize_transaction({
            "platform": "flipkart",
            "gstin": "07ABCDE1234F1Z5",
            "etin": "29AACCF0683K1C8",
            "filing_period": "042026",
            "invoice_no": "CN1",
            "invoice_date": "2026-04-02",
            "doc_type": "credit_note",
            "buyer_state_code": "37",
            "taxable_value": 420,
            "gst_rate": 3,
            "igst": 12.6,
            "cgst": 0,
            "sgst": 0,
            "cess": 0,
        })
        self.assertEqual(txn["taxable_value"], Decimal("-420.00"))
        self.assertEqual(txn["igst"], Decimal("-12.60"))
        self.assertEqual(txn["validation_status"], "valid")

    def test_gstr1_groups_by_supply_rate_pos_and_operator(self):
        rows = [
            finalize_transaction({
                "platform": "meesho",
                "gstin": "07ABCDE1234F1Z5",
                "etin": "07AARCM9332R1CQ",
                "filing_period": "042026",
                "invoice_no": "S1",
                "invoice_date": "2026-04-01",
                "doc_type": "invoice",
                "buyer_state_code": "37",
                "taxable_value": 1000,
                "gst_rate": 3,
                "igst": 30,
                "cess": 0,
            }),
            finalize_transaction({
                "platform": "meesho",
                "gstin": "07ABCDE1234F1Z5",
                "etin": "07AARCM9332R1CQ",
                "filing_period": "042026",
                "invoice_no": "CN1",
                "invoice_date": "2026-04-03",
                "doc_type": "credit_note",
                "buyer_state_code": "37",
                "taxable_value": 100,
                "gst_rate": 3,
                "igst": 3,
                "cess": 0,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows)
        self.assertEqual(payload["b2cs"][0]["txval"], 900.0)
        self.assertEqual(payload["b2cs"][0]["iamt"], 27.0)
        self.assertEqual(payload["supeco"]["supeco_det"][0]["suppval"], 900.0)
        self.assertEqual(len(payload["doc_issue"]["doc_det"]), 2)

    def test_real_marketplace_files_match_official_summary(self):
        paths = {
            "flipkart": "/home/jarvis/Downloads/d5407d8e-bffa-4b10-8a44-6cace40f5f48_1778999957000.xlsx",
            "meesho_sales": "/home/jarvis/Downloads/gst_3412749_4_2026/tcs_sales.xlsx",
            "meesho_returns": "/home/jarvis/Downloads/gst_3412749_4_2026/tcs_sales_return.xlsx",
            "meesho_invoice": "/home/jarvis/Downloads/3412749_2026-04-01_2026-04-30_TAX_INVOICE/Tax_invoice_details.xlsx",
            "amazon": "/home/jarvis/Downloads/b2cReport_April_2026/MTR_B2C-APRIL-2026-A1YGIWFZR88S6S.csv",
        }
        if not all(__import__("pathlib").Path(path).exists() for path in paths.values()):
            self.skipTest("Real marketplace sample files are not available on this machine.")
        summary = calculate_marketplace_summary(paths)
        combined = summary["combined"]
        flipkart = summary["platform_summary"]["Flipkart"]
        self.assertEqual(combined["taxable"], Decimal("21565.87"))
        self.assertEqual(combined["igst"], Decimal("628.95"))
        self.assertEqual(combined["cgst"], Decimal("9.01"))
        self.assertEqual(combined["sgst"], Decimal("9.01"))
        self.assertEqual(combined["total_gst"], Decimal("646.97"))
        self.assertEqual(flipkart["taxable"], Decimal("743.71"))
        self.assertEqual(flipkart["igst"], Decimal("22.29"))
        self.assertEqual(summary["document_counts"]["invoice"], 190)
        self.assertEqual(summary["document_counts"]["credit_note"], 46)
        self.assertEqual(summary["document_counts"]["debit_note"], 2)


if __name__ == "__main__":
    unittest.main()
