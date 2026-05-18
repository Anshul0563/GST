import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.generate_real_gstr1_json import build_payload_and_summary, validate  # noqa: E402


class RealGstr1JsonExportTests(unittest.TestCase):
    def test_generated_json_matches_original_gst_tool_json(self):
        original_path = Path("/home/jarvis/Downloads/GSTR1_returns_07TCRPS8655B1ZK_monthly_042026.json")
        if not original_path.exists():
            self.skipTest("Original GST Tool JSON file is not available on this machine.")

        payload, summary = build_payload_and_summary()
        original = json.loads(original_path.read_text(encoding="utf-8"))
        checks, failures = validate(summary, payload)

        self.assertEqual(failures, {})
        self.assertEqual(payload, original)
        self.assertEqual(checks["b2cs_records"], 24)
        self.assertEqual(checks["b2cs_taxable"], Decimal("21565.88"))
        self.assertEqual(checks["b2cs_igst"], Decimal("628.95"))
        self.assertEqual(checks["b2cs_cgst"], Decimal("9.01"))
        self.assertEqual(checks["b2cs_sgst"], Decimal("9.01"))
        self.assertEqual(checks["invoice_count"], 190)
        self.assertEqual(checks["credit_note_count"], 46)
        self.assertEqual(checks["debit_note_count"], 2)


if __name__ == "__main__":
    unittest.main()
