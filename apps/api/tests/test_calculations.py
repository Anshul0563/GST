import unittest
from decimal import Decimal

from app.services.gst import build_gstr1_json
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money


class GstCalculationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
