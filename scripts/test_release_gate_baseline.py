from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.release_gate import diff_against_baseline


class ReleaseGateBaselineTests(unittest.TestCase):
    def test_regression_from_exact_to_diagnose_is_flagged(self) -> None:
        baseline = {
            "source_states": [
                {"source_id": "codex", "state": "exact"},
                {"source_id": "claude-desktop", "state": "exact"},
            ]
        }
        current = {
            "source_states": [
                {"source_id": "codex", "state": "exact"},
                {"source_id": "claude-desktop", "state": "diagnose"},
            ]
        }

        delta = diff_against_baseline(current, baseline)

        self.assertIn("claude-desktop", delta["regressed"])
        self.assertNotIn("claude-desktop", delta["improved"])
        self.assertEqual(delta["counts"]["regressed"], 1)
        self.assertEqual(delta["counts"]["improved"], 0)


if __name__ == "__main__":
    unittest.main()
