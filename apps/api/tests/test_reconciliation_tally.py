import unittest
from decimal import Decimal

from app.services.reconciliation import ReconSettings, reconcile
from app.services.tally import build_tally_xml, build_vouchers, validate_tally_xml


class ReconciliationAndTallyTests(unittest.TestCase):
    def test_reconciliation_exact_tax_and_missing_categories(self):
        books = [
            {"supplier_gstin": "07ABCDE1234F1Z5", "invoice_no": "INV-1", "invoice_key": "inv1", "taxable_value": Decimal("1000"), "igst": Decimal("180"), "cgst": Decimal("0"), "sgst": Decimal("0"), "total_tax": Decimal("180")},
            {"supplier_gstin": "07ABCDE1234F1Z5", "invoice_no": "INV-2", "invoice_key": "inv2", "taxable_value": Decimal("500"), "igst": Decimal("90"), "cgst": Decimal("0"), "sgst": Decimal("0"), "total_tax": Decimal("90")},
        ]
        portal = [
            {"supplier_gstin": "07ABCDE1234F1Z5", "invoice_no": "INV-1", "invoice_key": "inv1", "taxable_value": Decimal("1000"), "igst": Decimal("180"), "cgst": Decimal("0"), "sgst": Decimal("0"), "total_tax": Decimal("180")},
            {"supplier_gstin": "07ABCDE1234F1Z5", "invoice_no": "INV-3", "invoice_key": "inv3", "taxable_value": Decimal("700"), "igst": Decimal("126"), "cgst": Decimal("0"), "sgst": Decimal("0"), "total_tax": Decimal("126")},
        ]
        rows, summary = reconcile(books, portal, ReconSettings())
        categories = [row["category"] for row in rows]
        self.assertIn("matched", categories)
        self.assertIn("missing_in_portal", categories)
        self.assertIn("missing_in_books", categories)
        self.assertEqual(summary["matched"], 1)

    def test_tally_xml_contains_sales_and_credit_note_vouchers(self):
        rows = [
            {"id": 1, "invoice_no": "S-1", "invoice_date": "2026-04-01", "doc_type": "invoice", "taxable_value": 1000, "igst": 30, "cgst": 0, "sgst": 0, "qty": 1, "product_name": "Item A"},
            {"id": 2, "invoice_no": "CN-1", "invoice_date": "2026-04-02", "doc_type": "credit_note", "taxable_value": -100, "igst": -3, "cgst": 0, "sgst": 0, "qty": -1, "product_name": "Item A"},
        ]
        vouchers = build_vouchers(rows)
        xml = build_tally_xml("GST Bharat Demo", rows)
        validation = validate_tally_xml(xml, vouchers)
        self.assertTrue(validation["valid"])
        self.assertIn('VCHTYPE="Sales"', xml)
        self.assertIn('VCHTYPE="Credit Note"', xml)
        self.assertEqual(validation["voucher_count"], 2)


if __name__ == "__main__":
    unittest.main()
