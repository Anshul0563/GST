import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from app.parsers.amazon import AmazonParser
from app.parsers.flipkart import FlipkartParser
from app.parsers.meesho import MeeshoParser
from app.services.excel_export import write_gstr1_excel
from app.services.gst import CLEAN_PORTAL, GSTTOOL_COMPATIBLE, build_gstr1_json, gstr1_generation_report
from app.services.gsttool_parity_validator import compare_against_reference
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

    def test_amazon_zero_value_cancel_without_invoice_is_skipped(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "amazon.csv"
            path.write_text(
                '"Seller Gstin","Invoice Number","Invoice Date","Transaction Type","Order Id","Shipment Item Id","Quantity","Ship To State","Invoice Amount","Tax Exclusive Gross","Igst Rate","Igst Tax"\n'
                '07TCRPS8655B1ZK,,"2026-03-12 19:15:27",Cancel,408-4473300-5420329,556794094160,1,ODISHA,0,0,0,0\n'
            )
            result = AmazonParser("07TCRPS8655B1ZK", "032026").parse([path])

        self.assertEqual(result.errors, [])
        self.assertEqual(result.transactions, [])

    def test_flipkart_cashback_document_number_and_tcs_are_parsed(self):
        parser = FlipkartParser("07TCRPS8655B1ZK", "032026")
        txn = parser.normalize_row({
            "Seller GSTIN": "07TCRPS8655B1ZK",
            "Order ID": "OD337009368354503100",
            "Order Item ID": "337009368354503100",
            "Document Type": "Credit Note",
            "Credit Note ID/ Debit Note ID": "CANQ1W2600000015",
            "Invoice Amount": "8.0",
            "Invoice Date": "2026-03-11 00:00:00.0",
            "Taxable Value": "7.77",
            "IGST Rate": "3.0",
            "IGST Amount": "0.23",
            "TCS IGST Rate": "0.5",
            "TCS IGST Amount": "0.039",
            "Total TCS Deducted": "0.04",
            "Customer's Delivery State": "Madhya Pradesh",
            "TDS Rate": "0.1",
            "TDS Amount": "0.008",
        }, "flipkart.xlsx:Cash Back Report")
        txn["doc_type"] = "credit_note"
        txn = finalize_transaction(txn)

        self.assertEqual(txn["invoice_no"], "CANQ1W2600000015")
        self.assertEqual(txn["buyer_state_code"], "23")
        self.assertEqual(txn["tcs"], Decimal("-0.04"))
        self.assertEqual(txn["tds"], Decimal("-0.01"))
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

    def test_intra_state_aggregate_split_is_stable_with_one_paise_drift(self):
        rows = [
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": "A1", "doc_type": "invoice", "buyer_state_code": "07", "taxable_value": 333.33, "gst_rate": 3, "cgst": 5, "sgst": 5,
            }),
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": "A2", "doc_type": "invoice", "buyer_state_code": "07", "taxable_value": 346.67, "gst_rate": 3, "cgst": 5.2, "sgst": 5.2,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows, CLEAN_PORTAL)
        intra = next(item for item in payload["b2cs"] if item["sply_ty"] == "INTRA")

        self.assertLessEqual(abs(Decimal(str(intra["camt"])) - Decimal(str(intra["samt"]))), Decimal("0.01"))
        self.assertEqual(Decimal(str(intra["camt"])) + Decimal(str(intra["samt"])), Decimal("20.40"))

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
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows, CLEAN_PORTAL)
        self.assertEqual(payload["b2cs"][0]["txval"], 900.0)
        self.assertEqual(payload["b2cs"][0]["iamt"], 27.0)
        self.assertEqual(payload["supeco"]["clttx"][0]["suppval"], 900.0)
        self.assertEqual(len(payload["doc_issue"]["doc_det"]), 2)
        self.assertEqual(payload["hash"], "hash")
        self.assertEqual(payload["doc_issue"]["doc_det"][0]["doc_typ"], "Invoices for outward supply")

    def test_gstr1_excludes_invalid_and_zero_b2cs_rows(self):
        rows = [
            finalize_transaction({
                "platform": "amazon",
                "gstin": "07ABCDE1234F1Z5",
                "etin": "07AAICA3918J1CV",
                "filing_period": "042026",
                "invoice_no": "IN-1",
                "doc_type": "invoice",
                "buyer_state_code": "27",
                "taxable_value": 100,
                "gst_rate": 3,
                "igst": 3,
            }),
            finalize_transaction({
                "platform": "amazon",
                "gstin": "07ABCDE1234F1Z5",
                "etin": "07AAICA3918J1CV",
                "filing_period": "042026",
                "invoice_no": "IN-ZERO",
                "doc_type": "invoice",
                "buyer_state_code": "27",
                "taxable_value": 0,
                "gst_rate": 0,
                "igst": 0,
            }),
            finalize_transaction({
                "platform": "amazon",
                "gstin": "07ABCDE1234F1Z5",
                "etin": "07AAICA3918J1CV",
                "filing_period": "042026",
                "invoice_no": "IN-NOPOS",
                "doc_type": "invoice",
                "taxable_value": 100,
                "gst_rate": 3,
                "igst": 3,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows, CLEAN_PORTAL)
        self.assertEqual(len(payload["b2cs"]), 1)
        self.assertEqual(payload["b2cs"][0]["rt"], 3)
        self.assertNotIn("supeco_det", payload["supeco"])

    def test_document_series_grouping_keeps_platform_prefixes_separate(self):
        rows = [
            finalize_transaction({
                "platform": "meesho", "gstin": "07ABCDE1234F1Z5", "etin": "07AARCM9332R1CQ", "filing_period": "042026",
                "invoice_no": "6p5kc26133", "doc_type": "invoice", "buyer_state_code": "37", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            }),
            finalize_transaction({
                "platform": "flipkart", "gstin": "07ABCDE1234F1Z5", "etin": "07AACCF0683K1CU", "filing_period": "042026",
                "invoice_no": "LWABOG7260000005", "doc_type": "invoice", "buyer_state_code": "37", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows, CLEAN_PORTAL)
        invoice_doc = next(item for item in payload["doc_issue"]["doc_det"] if item["doc_num"] == 1)
        self.assertEqual(len(invoice_doc["docs"]), 2)

    def test_document_series_with_gaps_splits_ranges(self):
        rows = [
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": invoice_no, "doc_type": "invoice", "buyer_state_code": "27", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            })
            for invoice_no in ("IN-5", "IN-6", "IN-8", "IN-9")
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows, CLEAN_PORTAL)
        invoice_doc = next(item for item in payload["doc_issue"]["doc_det"] if item["doc_num"] == 1)
        ranges = [(item["from"], item["to"], item["totnum"]) for item in invoice_doc["docs"]]
        self.assertEqual(ranges, [("IN-5", "IN-6", 2), ("IN-8", "IN-9", 2)])
        self.assertEqual(gstr1_generation_report(payload, rows)["errors"], [])

    def test_gsttool_mode_preserves_zero_b2cs_rows(self):
        row = finalize_transaction({
            "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
            "invoice_no": "IN-ZERO", "doc_type": "invoice", "buyer_state_code": "18", "taxable_value": 0, "gst_rate": 3, "igst": 0,
        })
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], GSTTOOL_COMPATIBLE)
        clean_payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], CLEAN_PORTAL)

        self.assertIn({"sply_ty": "INTER", "rt": 3, "typ": "OE", "pos": "18", "txval": 0, "iamt": 0, "csamt": 0}, payload["b2cs"])
        self.assertEqual({row["pos"] for row in payload["b2cs"]}, {"18"})
        self.assertEqual(clean_payload["b2cs"], [])

    def test_gsttool_mode_preserves_negative_b2cs_rows(self):
        row = finalize_transaction({
            "platform": "meesho", "gstin": "07ABCDE1234F1Z5", "etin": "07AARCM9332R1CQ", "filing_period": "042026",
            "invoice_no": "CN-NEG", "doc_type": "credit_note", "buyer_state_code": "36", "taxable_value": 100, "gst_rate": 3, "igst": 3,
        })
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], GSTTOOL_COMPATIBLE)
        clean_payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], CLEAN_PORTAL)

        self.assertEqual(payload["b2cs"], [{"sply_ty": "INTER", "rt": 3, "typ": "OE", "pos": "36", "txval": -97.09, "iamt": -3, "csamt": 0}])
        self.assertEqual(clean_payload["b2cs"], [])

    def test_gstr1_generation_filters_rows_by_requested_period(self):
        rows = [
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "022026",
                "invoice_no": "IN-FEB", "doc_type": "invoice", "buyer_state_code": "27", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            }),
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "032026",
                "invoice_no": "IN-MAR", "doc_type": "invoice", "buyer_state_code": "29", "taxable_value": 200, "gst_rate": 3, "igst": 6,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "022026", rows, GSTTOOL_COMPATIBLE)

        self.assertEqual([row["pos"] for row in payload["b2cs"]], ["27"])
        self.assertEqual(payload["doc_issue"]["doc_det"][0]["docs"][0]["from"], "IN-FEB")

    def test_gsttool_mode_merges_cross_prefix_document_ranges(self):
        rows = [
            finalize_transaction({
                "platform": "flipkart", "source_file": "flipkart.xlsx:Sales Report", "gstin": "07ABCDE1234F1Z5", "etin": "07AACCF0683K1CU", "filing_period": "032026",
                "invoice_no": invoice_no, "doc_type": "invoice", "buyer_state_code": "37", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            })
            for invoice_no in ("FAWRLX2600000080", "LWABOG7260000005")
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "032026", rows, GSTTOOL_COMPATIBLE)
        clean_payload = build_gstr1_json("07ABCDE1234F1Z5", "032026", rows, CLEAN_PORTAL)
        gsttool_ranges = payload["doc_issue"]["doc_det"][0]["docs"]
        clean_ranges = clean_payload["doc_issue"]["doc_det"][0]["docs"]

        self.assertEqual(gsttool_ranges, [{"num": 1, "from": "FAWRLX2600000080", "to": "LWABOG7260000005", "totnum": 2, "cancel": 0, "net_issue": 2}])
        self.assertEqual(len(clean_ranges), 2)

    def test_gsttool_mode_preserves_source_cgst_sgst_rounding(self):
        row = {
            "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
            "invoice_no": "A1", "doc_type": "invoice", "buyer_state_code": "07", "taxable_value": 100, "gst_rate": 3, "cgst": 1.49, "sgst": 1.50,
            "igst": 0, "cess": 0, "validation_status": "valid",
        }
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], GSTTOOL_COMPATIBLE)
        clean_payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", [row], CLEAN_PORTAL)

        gsttool_row = next(row for row in payload["b2cs"] if row.get("pos") == "07")
        self.assertEqual(gsttool_row["camt"], 1.49)
        self.assertEqual(gsttool_row["samt"], 1.5)
        self.assertEqual(clean_payload["b2cs"][0]["camt"], 1.5)
        self.assertEqual(clean_payload["b2cs"][0]["samt"], 1.49)

    def test_gsttool_mode_uses_flipkart_operator_level_supeco_rounding(self):
        row = {
            "platform": "flipkart", "gstin": "07ABCDE1234F1Z5", "etin": "07AACCF0683K1CU", "filing_period": "032026",
            "invoice_no": "LWABOG7260000002", "doc_type": "invoice", "buyer_state_code": "07", "taxable_value": 99.02,
            "gst_rate": 3, "igst": 0, "cgst": 1.50, "sgst": 1.49, "cess": 0, "validation_status": "valid",
        }
        payload = build_gstr1_json("07ABCDE1234F1Z5", "032026", [row], GSTTOOL_COMPATIBLE)
        clean_payload = build_gstr1_json("07ABCDE1234F1Z5", "032026", [row], CLEAN_PORTAL)

        gsttool_eco = next(row for row in payload["supeco"]["clttx"] if row["etin"] == "07AACCF0683K1CU")
        clean_eco = next(row for row in clean_payload["supeco"]["clttx"] if row["etin"] == "07AACCF0683K1CU")
        self.assertEqual(gsttool_eco["cgst"], 1.49)
        self.assertEqual(gsttool_eco["sgst"], 1.49)
        self.assertEqual(clean_eco["cgst"], 1.5)
        self.assertEqual(clean_eco["sgst"], 1.49)

    def test_gsttool_parity_validator_matches_reference_json(self):
        reference = {
            "gstin": "07ABCDE1234F1Z5",
            "fp": "032026",
            "version": "GST3.1.6",
            "hash": "hash",
            "b2cs": [{"sply_ty": "INTER", "rt": 3, "typ": "OE", "pos": "18", "txval": 0, "iamt": 0, "csamt": 0}],
            "supeco": {"clttx": []},
            "doc_issue": {"doc_det": [{"doc_num": 1, "doc_typ": "Invoices for outward supply", "docs": [{"num": 1, "from": "FAWRLX2600000080", "to": "LWABOG7260000005", "totnum": 2, "cancel": 0, "net_issue": 2}]}]},
        }
        report = compare_against_reference(reference, reference)

        self.assertTrue(report["exact_match"])
        self.assertEqual(report["match_score"], 100.0)

    def test_uploaded_platform_without_valid_rows_warns_without_zero_supeco(self):
        rows = [
            finalize_transaction({
                "platform": "meesho", "gstin": "07ABCDE1234F1Z5", "etin": "07AARCM9332R1CQ", "filing_period": "042026",
                "invoice_no": "6p5kc26133", "doc_type": "invoice", "buyer_state_code": "37", "taxable_value": 0, "gst_rate": 0, "igst": 0,
            }),
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": "IN-5", "doc_type": "invoice", "buyer_state_code": "27", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows)
        etins = [item["etin"] for item in payload["supeco"]["clttx"]]
        report = gstr1_generation_report(payload, rows)
        self.assertNotIn("07AARCM9332R1CQ", etins)
        self.assertIn("No valid Meesho rows found for period 042026", report["warnings"])

    def test_meesho_parser_joins_financial_rows_with_invoice_metadata(self):
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            sales = base / "tcs_sales.xlsx"
            returns = base / "tcs_sales_return.xlsx"
            invoice = base / "Tax_invoice_details.xlsx"
            pd.DataFrame([{
                "sub order num": "SO-1",
                "order date": "2026-03-22",
                "hsn code": "711790",
                "quantity": 1,
                "gst rate": 3,
                "total taxable sale value": 100,
                "tax amount": 3,
                "total invoice value": 103,
                "end customer state new": "TELANGANA",
                "eco tcs gstin": "07AARCM9332R1CQ",
            }]).to_excel(sales, index=False)
            pd.DataFrame([{
                "sub order num": "SO-2",
                "order date": "2026-03-23",
                "hsn code": "711790",
                "quantity": 1,
                "gst rate": 3,
                "total taxable sale value": 50,
                "tax amount": 1.5,
                "total invoice value": 51.5,
                "end customer state new": "KARNATAKA",
                "eco tcs gstin": "07AARCM9332R1CQ",
            }]).to_excel(returns, index=False)
            pd.DataFrame([
                {"type": "INVOICE", "order date": "2026-03-22", "suborder no.": "SO-1", "product description": "Jewellery", "hsn": "711790", "invoice no.": "6p5kc26244"},
                {"type": "CREDIT", "order date": "2026-03-23", "suborder no.": "SO-2", "product description": "Jewellery", "hsn": "711790", "invoice no.": "6p5kcC26244"},
            ]).to_excel(invoice, sheet_name="Invoice_Info", index=False)

            result = MeeshoParser("07TCRPS8655B1ZK", "032026").parse([sales, returns, invoice])

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.transactions), 2)
        invoices = {txn["invoice_no"]: txn for txn in result.transactions}
        self.assertEqual(invoices["6p5kc26244"]["validation_status"], "valid")
        self.assertEqual(invoices["6p5kc26244"]["buyer_state_code"], "36")
        self.assertEqual(invoices["6p5kc26244"]["taxable_value"], Decimal("100.00"))
        self.assertEqual(invoices["6p5kcC26244"]["doc_type"], "credit_note")
        self.assertEqual(invoices["6p5kcC26244"]["taxable_value"], Decimal("-50.00"))

    def test_meesho_parser_uses_suborder_fallback_when_invoice_metadata_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            returns = base / "tcs_sales_return.xlsx"
            invoice = base / "Tax_invoice_details.xlsx"
            pd.DataFrame([{
                "sub order num": "SO-MISSING",
                "order date": "2026-03-23",
                "hsn code": "711790",
                "quantity": 1,
                "gst rate": 3,
                "total taxable sale value": 50,
                "tax amount": 1.5,
                "total invoice value": 51.5,
                "end customer state new": "KARNATAKA",
                "eco tcs gstin": "07AARCM9332R1CQ",
            }]).to_excel(returns, index=False)
            pd.DataFrame([{
                "type": "INVOICE",
                "order date": "2026-03-22",
                "suborder no.": "OTHER",
                "hsn": "711790",
                "invoice no.": "6p5kc26244",
            }]).to_excel(invoice, sheet_name="Invoice_Info", index=False)

            result = MeeshoParser("07TCRPS8655B1ZK", "032026").parse([returns, invoice])

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.transactions), 1)
        self.assertEqual(result.transactions[0]["invoice_no"], "SO-MISSING")
        self.assertEqual(result.transactions[0]["doc_type"], "credit_note")
        self.assertEqual(result.transactions[0]["validation_status"], "valid")

    def test_gstr1_json_contract_matches_offline_tool_structure(self):
        rows = [
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": "IN-1", "doc_type": "invoice", "buyer_state_code": "27", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            }),
            finalize_transaction({
                "platform": "amazon", "gstin": "07ABCDE1234F1Z5", "etin": "07AAICA3918J1CV", "filing_period": "042026",
                "invoice_no": "CN-1", "doc_type": "credit_note", "buyer_state_code": "27", "taxable_value": 10, "gst_rate": 3, "igst": 0.3,
            }),
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows)

        self.assertEqual(list(payload.keys()), ["gstin", "fp", "version", "hash", "b2cs", "supeco", "doc_issue"])
        self.assertEqual(payload["hash"], "hash")
        self.assertEqual(set(payload["supeco"].keys()), {"clttx"})
        self.assertNotIn("supeco_det", payload["supeco"])
        self.assertEqual(set(payload["b2cs"][0].keys()), {"sply_ty", "rt", "typ", "pos", "txval", "iamt", "csamt"})
        self.assertTrue(all(set(section.keys()) == {"doc_num", "doc_typ", "docs"} for section in payload["doc_issue"]["doc_det"]))
        self.assertTrue(all(set(doc.keys()) == {"num", "from", "to", "totnum", "cancel", "net_issue"} for section in payload["doc_issue"]["doc_det"] for doc in section["docs"]))

    def test_gstr1_report_blocks_schema_drift_and_fake_rows(self):
        payload = {
            "gstin": "07ABCDE1234F1Z5",
            "fp": "042026",
            "version": "GST3.1.6",
            "hash": "bad",
            "b2cs": [{"sply_ty": "INTER", "rt": 0, "typ": "OE", "pos": "27", "txval": 0, "iamt": 0, "csamt": 0}],
            "supeco": {"supeco_det": []},
            "doc_issue": {"doc_det": [{"doc_num": 1, "doc_typ": "Wrong", "docs": [{"num": 1, "from": "IN-1", "to": "IN-3", "totnum": 2, "cancel": 0, "net_issue": 2}]}]},
        }
        report = gstr1_generation_report(payload, [])

        self.assertTrue(any("hash" in error for error in report["errors"]))
        self.assertTrue(any("SUPECO" in error for error in report["errors"]))
        self.assertTrue(any("fake" in error.lower() or "rate" in error.lower() for error in report["errors"]))
        self.assertTrue(any("implies 3 documents" in error for error in report["errors"]))

    def test_gstr1_excel_contract_matches_offline_tool_sheet_layout(self):
        rows = [
            finalize_transaction({
                "platform": "meesho", "gstin": "07ABCDE1234F1Z5", "etin": "07AARCM9332R1CQ", "filing_period": "042026",
                "invoice_no": "6p5kc271", "doc_type": "invoice", "buyer_state_code": "37", "taxable_value": 100, "gst_rate": 3, "igst": 3,
            })
        ]
        payload = build_gstr1_json("07ABCDE1234F1Z5", "042026", rows)
        with TemporaryDirectory() as temp_dir:
            path = write_gstr1_excel(Path(temp_dir) / "gstr1.xlsx", payload, rows)
            xl = pd.ExcelFile(path)
            self.assertEqual(xl.sheet_names, ["b2b,sez,de", "b2cl", "b2cs", "cdnr", "hsn", "hsn(b2b)", "hsn(b2c)", "exemp", "eco", "docs"])
            b2cs = pd.read_excel(path, sheet_name="b2cs", header=None, dtype=object)
            eco = pd.read_excel(path, sheet_name="eco", header=None, dtype=object)
            docs = pd.read_excel(path, sheet_name="docs", header=None, dtype=object)

        self.assertEqual(list(b2cs.iloc[3, :7]), ["Type", "Place Of Supply", "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"])
        self.assertEqual(b2cs.iloc[4, 1], "37-Andhra Pradesh")
        self.assertEqual(list(eco.iloc[3, :8]), ["Nature of Supply", "GSTIN of E-Commerce Operator", "E-Commerce Operator Name", "Net value of supplies", "Integrated tax", "Central tax", "State/UT tax", "Cess"])
        self.assertEqual(eco.iloc[4, 1], "07AARCM9332R1CQ")
        self.assertEqual(list(docs.iloc[3, :5]), ["Nature of Document", "Sr. No. From", "Sr. No. To", "Total Number", "Cancelled"])

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
