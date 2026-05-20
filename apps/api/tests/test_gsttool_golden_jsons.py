import copy
import json
import unittest
from pathlib import Path

from app.parsers.amazon import AmazonParser
from app.parsers.flipkart import FlipkartParser
from app.parsers.meesho import MeeshoParser
from app.services.gst import GSTTOOL_COMPATIBLE, build_gstr1_json
from app.services.gsttool_parity_validator import compare_against_reference


class GstToolGoldenJsonTests(unittest.TestCase):
    def test_original_march_json_preserves_gsttool_quirks(self):
        path = Path("/home/jarvis/Downloads/GSTR1_returns_07TCRPS8655B1ZK_monthly_032026.json")
        if not path.exists():
            self.skipTest("Original March GSTTool JSON is not available on this machine.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        zero_pos = {row["pos"] for row in payload["b2cs"] if row.get("txval") == 0 and row.get("iamt") == 0}
        doc_ranges = {
            (doc["from"], doc["to"])
            for section in payload["doc_issue"]["doc_det"]
            for doc in section["docs"]
        }
        report = compare_against_reference(payload, copy.deepcopy(payload))

        self.assertTrue({"18", "04", "06", "20"}.issubset(zero_pos))
        self.assertIn(("FAWRLX2600000080", "LWABOG7260000005"), doc_ranges)
        self.assertIn(("MFABNVY260000001", "RAT6SO2600000034"), doc_ranges)
        self.assertIn(("CANQ1W2600000013", "LYAA9U7260000001"), doc_ranges)
        self.assertIn(("DAL84U2600000005", "LZAA9B7260000001"), doc_ranges)
        self.assertTrue(report["exact_match"])
        self.assertEqual(report["match_score"], 100.0)

    def test_april_golden_json_matches_parity_contract(self):
        path = Path("exports/gst_bharat_gstr1_07TCRPS8655B1ZK_042026.json")
        if not path.exists():
            self.skipTest("April GSTTool-compatible golden JSON is not available.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        report = compare_against_reference(payload, copy.deepcopy(payload))

        self.assertEqual(list(payload.keys()), ["gstin", "fp", "version", "hash", "b2cs", "supeco", "doc_issue"])
        self.assertEqual(payload["fp"], "042026")
        self.assertEqual([row["etin"] for row in payload["supeco"]["clttx"]], ["07AARCM9332R1CQ", "07AACCF0683K1CU", "07AAICA3918J1CV"])
        self.assertTrue(report["exact_match"])
        self.assertEqual(report["match_score"], 100.0)

    def test_march_raw_marketplace_files_rebuild_original_gsttool_json_exactly(self):
        reference_path = Path("/home/jarvis/Downloads/GSTR1_returns_07TCRPS8655B1ZK_monthly_032026.json")
        raw_paths = {
            "amazon": Path("/home/jarvis/Downloads/MTR_B2C-MARCH-2026-A1YGIWFZR88S6S.csv"),
            "flipkart": Path("/home/jarvis/Downloads/11d11828-0221-4866-b714-b5a26595f116_1779106486000.xlsx"),
            "meesho_sales": Path("/home/jarvis/Downloads/tcs_sales.xlsx"),
            "meesho_returns": Path("/home/jarvis/Downloads/tcs_sales_return.xlsx"),
            "meesho_invoice": Path("/home/jarvis/Downloads/Tax_invoice_details.xlsx"),
        }
        if not reference_path.exists() or not all(path.exists() for path in raw_paths.values()):
            self.skipTest("Original March GSTTool JSON and raw marketplace files are not available.")

        gstin = "07TCRPS8655B1ZK"
        period = "032026"
        rows = []
        rows.extend(AmazonParser(gstin, period).parse([raw_paths["amazon"]]).transactions)
        rows.extend(FlipkartParser(gstin, period).parse([raw_paths["flipkart"]]).transactions)
        rows.extend(
            MeeshoParser(gstin, period)
            .parse([raw_paths["meesho_sales"], raw_paths["meesho_returns"], raw_paths["meesho_invoice"]])
            .transactions
        )

        generated = build_gstr1_json(gstin, period, rows, GSTTOOL_COMPATIBLE)
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        report = compare_against_reference(reference, generated)

        self.assertTrue(report["exact_match"], report["differences"][:10])
        self.assertEqual(report["match_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
