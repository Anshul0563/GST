import copy
import json
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
