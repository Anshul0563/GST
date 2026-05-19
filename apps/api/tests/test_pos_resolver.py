import unittest
from decimal import Decimal

from app.services.pos_resolver import resolve_pos
from app.services.transaction_normalizer import finalize_transaction
from app.utils.states import state_code_from_text


class PosResolverTests(unittest.TestCase):
    def test_meesho_state_aliases(self):
        resolved = resolve_pos({"customer_state": "Odisha"}, {"gstin": "07ABCDE1234F1Z5"}, "meesho")
        self.assertEqual(resolved.buyer_state_code, "21")
        self.assertEqual(resolved.confidence, "high")

    def test_flipkart_state_aliases(self):
        resolved = resolve_pos({"Billing State": "Karnataka"}, {"gstin": "07ABCDE1234F1Z5"}, "flipkart")
        self.assertEqual(resolved.buyer_state_code, "29")

    def test_amazon_ship_state_aliases(self):
        resolved = resolve_pos({"ship-state": "MAHARASHTRA"}, {"gstin": "07ABCDE1234F1Z5"}, "amazon")
        self.assertEqual(resolved.buyer_state_code, "27")

    def test_custom_excel_aliases(self):
        resolved = resolve_pos({"Destination State": "Tamil Nadu"}, {"gstin": "07ABCDE1234F1Z5"}, "custom")
        self.assertEqual(resolved.buyer_state_code, "33")

    def test_state_code_normalization(self):
        self.assertEqual(state_code_from_text("1"), "01")
        self.assertEqual(state_code_from_text("01"), "01")

    def test_pincode_fallback(self):
        resolved = resolve_pos({"Customer Pincode": "560037"}, {"gstin": "07ABCDE1234F1Z5", "igst": 10}, "custom")
        self.assertEqual(resolved.buyer_state_code, "29")
        self.assertEqual(resolved.confidence, "inferred_from_pincode")
        self.assertTrue(resolved.warning)

    def test_daman_and_pondicherry_aliases(self):
        self.assertEqual(state_code_from_text("Daman"), "26")
        self.assertEqual(state_code_from_text("DNHDD"), "26")
        self.assertEqual(state_code_from_text("Pondicherry"), "34")

    def test_cgst_sgst_same_state_fallback(self):
        resolved = resolve_pos({}, {"gstin": "07ABCDE1234F1Z5", "cgst": 5, "sgst": 5}, "custom")
        self.assertEqual(resolved.buyer_state_code, "07")
        self.assertEqual(resolved.confidence, "inferred_from_seller_state")
        self.assertTrue(resolved.warning)

    def test_gst_rate_rounds_to_nearest_slab(self):
        txn = finalize_transaction({
            "platform": "flipkart",
            "gstin": "07ABCDE1234F1Z5",
            "etin": "07AACCF0683K1CU",
            "filing_period": "032026",
            "invoice_no": "F1",
            "invoice_date": "2026-03-01",
            "buyer_state_code": "29",
            "taxable_value": 99.02,
            "gst_rate": 0,
            "igst": 2.99,
            "cgst": 0,
            "sgst": 0,
            "cess": 0,
        })
        self.assertEqual(txn["gst_rate"], Decimal("3"))
        self.assertEqual(txn["validation_status"], "valid")


if __name__ == "__main__":
    unittest.main()
