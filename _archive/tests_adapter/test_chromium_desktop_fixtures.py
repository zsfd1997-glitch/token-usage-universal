from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.chromium_desktop_family import build_chromium_desktop_family_adapters
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


class ChromiumDesktopFixtureTests(unittest.TestCase):
    def test_every_chromium_desktop_source_has_exact_fixture(self) -> None:
        for adapter in build_chromium_desktop_family_adapters():
            fixture_root = FIXTURE_ROOT / adapter.source_id / "exact"
            with self.subTest(source_id=adapter.source_id):
                self.assertTrue(fixture_root.is_dir(), f"{adapter.source_id} 缺少 exact fixture: {fixture_root}")
                adapter.root = fixture_root
                detection = adapter.detect()
                result = adapter.collect(_window())

                self.assertTrue(detection.available)
                self.assertEqual(detection.status, "ready")
                self.assertEqual(len(result.events), 1)
                self.assertEqual(result.events[0].source, adapter.source_id)
                self.assertGreater(result.events[0].total_tokens, 0)

    def test_every_chromium_desktop_source_has_diagnose_fixture(self) -> None:
        for adapter in build_chromium_desktop_family_adapters():
            fixture_root = FIXTURE_ROOT / adapter.source_id / "diagnose"
            with self.subTest(source_id=adapter.source_id):
                self.assertTrue(fixture_root.is_dir(), f"{adapter.source_id} 缺少 diagnose fixture: {fixture_root}")
                adapter.root = fixture_root
                detection = adapter.detect()
                result = adapter.collect(_window())

                self.assertFalse(detection.available)
                self.assertEqual(detection.status, "not-found")
                self.assertIn("exact", detection.summary.lower())
                self.assertEqual(result.events, [])
                self.assertIn(detection.summary, result.skipped_reasons)


if __name__ == "__main__":
    unittest.main()
