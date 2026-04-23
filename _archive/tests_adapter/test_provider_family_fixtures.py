from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.compatible_api_family import build_provider_api_adapters
from core.config import (
    TOKEN_USAGE_CACHE_ROOT_ENV,
    TOKEN_USAGE_DISCOVERY_ROOTS_ENV,
    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
)
from core.models import TimeWindow
from test_time import PACIFIC_TZ


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "provider"


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=PACIFIC_TZ),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=PACIFIC_TZ),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class ProviderFamilyFixtureTests(unittest.TestCase):
    def test_every_provider_family_has_exact_fixture(self) -> None:
        adapter_map = {adapter.source_id: adapter for adapter in build_provider_api_adapters()}

        for source_id in adapter_map:
            fixture = FIXTURE_ROOT / source_id / "exact.jsonl"
            with self.subTest(source_id=source_id):
                self.assertTrue(fixture.is_file(), f"{source_id} 缺少 exact fixture: {fixture}")
                with tempfile.TemporaryDirectory() as tmp:
                    with patch.dict(
                        os.environ,
                        {
                            TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(fixture),
                            TOKEN_USAGE_DISCOVERY_ROOTS_ENV: str(Path(tmp) / "unused"),
                            TOKEN_USAGE_CACHE_ROOT_ENV: str(Path(tmp) / "cache"),
                        },
                        clear=False,
                    ):
                        adapter = adapter_map[source_id]
                        detection = adapter.detect()
                        result = adapter.collect(_window())

                self.assertTrue(detection.available)
                self.assertEqual(detection.status, "ready")
                self.assertEqual(len(result.events), 1)
                self.assertEqual(result.events[0].source, source_id)
                self.assertGreater(result.events[0].total_tokens, 0)

    def test_every_provider_family_has_diagnose_fixture(self) -> None:
        adapter_map = {adapter.source_id: adapter for adapter in build_provider_api_adapters()}

        for source_id in adapter_map:
            fixture = FIXTURE_ROOT / source_id / "diagnose.jsonl"
            with self.subTest(source_id=source_id):
                self.assertTrue(fixture.is_file(), f"{source_id} 缺少 diagnose fixture: {fixture}")
                with tempfile.TemporaryDirectory() as tmp:
                    with patch.dict(
                        os.environ,
                        {
                            TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(fixture),
                            TOKEN_USAGE_DISCOVERY_ROOTS_ENV: str(Path(tmp) / "unused"),
                            TOKEN_USAGE_CACHE_ROOT_ENV: str(Path(tmp) / "cache"),
                        },
                        clear=False,
                    ):
                        adapter = adapter_map[source_id]
                        detection = adapter.detect()
                        result = adapter.collect(_window())

                self.assertFalse(detection.available)
                self.assertEqual(detection.status, "not-found")
                self.assertIn("exact", detection.summary.lower())
                self.assertEqual(result.events, [])
                self.assertIn(detection.summary, result.skipped_reasons)


if __name__ == "__main__":
    unittest.main()
