from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.time_window import build_time_window, resolve_timezone


class TimeWindowTests(unittest.TestCase):
    def test_resolve_timezone_falls_back_from_legacy_us_alias(self) -> None:
        real_zoneinfo = ZoneInfo

        def fake_zoneinfo(name: str):
            if name == "US/Pacific":
                raise ZoneInfoNotFoundError("legacy alias unavailable")
            return real_zoneinfo(name)

        with patch("core.time_window.ZoneInfo", side_effect=fake_zoneinfo):
            tzinfo = resolve_timezone("US/Pacific")

        self.assertEqual(getattr(tzinfo, "key", None), "America/Los_Angeles")

    def test_build_time_window_preserves_requested_timezone_name(self) -> None:
        window = build_time_window(today=True, last=None, start=None, end=None, tz_name="US/Pacific")

        self.assertEqual(window.timezone_name, "US/Pacific")


if __name__ == "__main__":
    unittest.main()
