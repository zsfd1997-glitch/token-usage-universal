from __future__ import annotations

import io
import sys
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import token_usage
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from test_time import PACIFIC_TZ


class _FakeAdapter:
    source_id = "fake"

    def __init__(self) -> None:
        self.collect_calls = 0
        self.collect_chart_calls = 0

    def _result(self) -> SourceCollectResult:
        tzinfo = PACIFIC_TZ
        detection = SourceDetection(
            source_id="fake",
            display_name="Fake",
            provider="openai",
            accuracy_level="exact",
            supported=True,
            available=True,
            summary="ready",
        )
        event = UsageEvent(
            source="fake",
            provider="openai",
            timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo),
            session_id="fake-session",
            project_path="/tmp/fake",
            model="gpt-5.4",
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=10,
            reasoning_tokens=5,
            total_tokens=115,
            accuracy_level="exact",
            raw_event_kind="unit-test",
            source_path="/tmp/fake.jsonl",
        )
        return SourceCollectResult(detection=detection, events=[event], scanned_files=1)

    def collect(self, window) -> SourceCollectResult:  # noqa: ANN001
        self.collect_calls += 1
        return self._result()

    def collect_chart(self, window) -> SourceCollectResult:  # noqa: ANN001
        self.collect_chart_calls += 1
        return self._result()


class TokenUsageFastPathTests(unittest.TestCase):
    def test_dashboard_recent_text_prefers_chart_fast_path(self) -> None:
        adapter = _FakeAdapter()
        args = Namespace(
            source=None,
            dashboard="recent",
            trend=None,
            calendar=None,
            today=False,
            last="30d",
            start=None,
            end=None,
            tz="US/Pacific",
            by=None,
            limit=5,
            month=None,
            session=None,
            estimated_cost=False,
            plain_ascii=False,
            format="text",
            current_session=False,
        )

        with patch.object(token_usage, "_build_adapters", return_value={"fake": adapter}):
            with io.StringIO() as buffer, redirect_stdout(buffer):
                exit_code = token_usage.command_report(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(adapter.collect_calls, 0)
        self.assertEqual(adapter.collect_chart_calls, 1)


if __name__ == "__main__":
    unittest.main()
