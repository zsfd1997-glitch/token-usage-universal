from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.claude_desktop import ClaudeDesktopAdapter
from adapters.minimax_agent import MiniMaxAgentAdapter
from core.models import TimeWindow
from test_time import PACIFIC_TZ


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "desktop"


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=PACIFIC_TZ),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=PACIFIC_TZ),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class NativeDesktopFixtureTests(unittest.TestCase):
    def test_claude_desktop_fixtures_cover_exact_and_diagnose(self) -> None:
        exact_adapter = ClaudeDesktopAdapter(root=FIXTURE_ROOT / "claude-desktop" / "exact")
        exact_detection = exact_adapter.detect()
        exact_result = exact_adapter.collect(_window())

        self.assertTrue(exact_detection.available)
        self.assertEqual(exact_detection.status, "ready")
        self.assertEqual(len(exact_result.events), 1)
        self.assertEqual(exact_result.events[0].source, "claude-desktop")
        self.assertGreater(exact_result.events[0].total_tokens, 0)

        diagnose_adapter = ClaudeDesktopAdapter(root=FIXTURE_ROOT / "claude-desktop" / "diagnose")
        diagnose_detection = diagnose_adapter.detect()
        diagnose_result = diagnose_adapter.collect(_window())

        self.assertFalse(diagnose_detection.available)
        self.assertEqual(diagnose_detection.status, "not-found")
        self.assertIn("exact", diagnose_detection.summary.lower())
        self.assertEqual(diagnose_result.events, [])
        self.assertIn(diagnose_detection.summary, diagnose_result.skipped_reasons)

    def test_minimax_agent_fixtures_cover_exact_and_diagnose(self) -> None:
        exact_adapter = MiniMaxAgentAdapter(root=FIXTURE_ROOT / "minimax-agent" / "exact")
        exact_detection = exact_adapter.detect()
        exact_result = exact_adapter.collect(_window())

        self.assertTrue(exact_detection.available)
        self.assertEqual(exact_detection.status, "ready")
        self.assertEqual(len(exact_result.events), 1)
        self.assertEqual(exact_result.events[0].source, "minimax-agent")
        self.assertGreater(exact_result.events[0].total_tokens, 0)

        diagnose_adapter = MiniMaxAgentAdapter(root=FIXTURE_ROOT / "minimax-agent" / "diagnose")
        diagnose_detection = diagnose_adapter.detect()
        diagnose_result = diagnose_adapter.collect(_window())

        self.assertFalse(diagnose_detection.available)
        self.assertEqual(diagnose_detection.status, "not-found")
        self.assertIn("exact", diagnose_detection.summary.lower())
        self.assertEqual(diagnose_result.events, [])
        self.assertIn(diagnose_detection.summary, diagnose_result.skipped_reasons)


if __name__ == "__main__":
    unittest.main()
