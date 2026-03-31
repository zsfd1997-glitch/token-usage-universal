from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from core.config import TOKEN_USAGE_CACHE_ROOT_ENV, TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
from core.models import TimeWindow


def _make_window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


def _window(start: datetime, end: datetime, label: str = "Custom") -> TimeWindow:
    return TimeWindow(
        start=start,
        end=end,
        label=label,
        timezone_name="US/Pacific",
    )


class GenericAdapterTests(unittest.TestCase):
    def test_detect_requires_explicit_glob_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            detection = GenericOpenAICompatibleAdapter().detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn(TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV, detection.summary)

    def test_detect_expands_windows_style_percent_variable_glob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "generic.jsonl"
            log_file.write_text("{}", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "GENERIC_LOG_ROOT": str(root),
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: "%GENERIC_LOG_ROOT%/*.jsonl",
                },
                clear=False,
            ):
                detection = GenericOpenAICompatibleAdapter().detect()

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertIn(str(log_file), detection.candidate_paths[0])

    def test_collect_reads_exact_usage_from_nested_usage_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "generic.jsonl"
            log_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-25T11:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-1",
                                "project_path": "/tmp/project-b",
                                "usage": {
                                    "input_tokens": 1200,
                                    "cached_input_tokens": 200,
                                    "output_tokens": 300,
                                    "reasoning_tokens": 40,
                                    "total_tokens": 1540,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T11:05:00-07:00",
                                "vendor": "zhipu",
                                "model_name": "glm-4.5",
                                "conversation_id": "generic-2",
                                "cwd": "/tmp/project-c",
                                "payload": {
                                    "usage": {
                                        "prompt_tokens": 1000,
                                        "completion_tokens": 220,
                                        "reasoning_output_tokens": 30,
                                        "total_tokens": 1250,
                                    }
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env_value = str(log_file)
            with patch.dict(
                os.environ,
                {TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: env_value},
                clear=False,
            ):
                result = GenericOpenAICompatibleAdapter().collect(_make_window())

            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(len(result.events), 2)
            self.assertEqual(result.events[0].model, "deepseek-chat")
            self.assertEqual(result.events[0].total_tokens, 1540)
            self.assertEqual(result.events[1].model, "glm-4.5")
            self.assertEqual(result.events[1].provider, "zhipu")
            self.assertEqual(result.events[1].input_tokens, 1000)
            self.assertEqual(result.events[1].output_tokens, 220)
            self.assertEqual(result.events[1].reasoning_tokens, 30)

    def test_collect_reports_no_exact_usage_when_records_lack_usage_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "generic.jsonl"
            log_file.write_text(
                json.dumps({"timestamp": "2026-03-25T11:00:00-07:00", "message": "hello"}) + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file)},
                clear=False,
            ):
                result = GenericOpenAICompatibleAdapter().collect(_make_window())

            self.assertEqual(result.events, [])
            self.assertIn("no exact usage records found", " ".join(result.verification_issues))

    def test_collect_reuses_incremental_cache_for_unchanged_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            log_file = root / "generic.jsonl"
            log_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-25T11:00:00-07:00",
                        "provider": "openai-compatible",
                        "model": "deepseek-chat",
                        "session_id": "generic-1",
                        "project_path": "/tmp/project-b",
                        "usage": {
                            "input_tokens": 1200,
                            "cached_input_tokens": 200,
                            "output_tokens": 300,
                            "reasoning_tokens": 40,
                            "total_tokens": 1540,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = GenericOpenAICompatibleAdapter()
                first = adapter.collect(_make_window())
                self.assertEqual(len(first.events), 1)
                with patch.object(adapter, "_collect_file", side_effect=AssertionError("cache miss")):
                    second = adapter.collect(_make_window())

            self.assertEqual(len(second.events), 1)

    def test_collect_invalidates_cache_after_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            log_file = root / "generic.jsonl"
            log_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-25T11:00:00-07:00",
                        "provider": "openai-compatible",
                        "model": "deepseek-chat",
                        "session_id": "generic-1",
                        "project_path": "/tmp/project-b",
                        "usage": {
                            "input_tokens": 1200,
                            "cached_input_tokens": 200,
                            "output_tokens": 300,
                            "reasoning_tokens": 40,
                            "total_tokens": 1540,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = GenericOpenAICompatibleAdapter()
                first = adapter.collect(_make_window())
                self.assertEqual(len(first.events), 1)
                log_file.write_text(
                    "\n".join(
                        [
                            json.dumps(
                                {
                                    "timestamp": "2026-03-25T11:00:00-07:00",
                                    "provider": "openai-compatible",
                                    "model": "deepseek-chat",
                                    "session_id": "generic-1",
                                    "project_path": "/tmp/project-b",
                                    "usage": {
                                        "input_tokens": 1200,
                                        "cached_input_tokens": 200,
                                        "output_tokens": 300,
                                        "reasoning_tokens": 40,
                                        "total_tokens": 1540,
                                    },
                                }
                            ),
                            json.dumps(
                                {
                                    "timestamp": "2026-03-25T11:10:00-07:00",
                                    "provider": "openai-compatible",
                                    "model": "glm-4.5",
                                    "session_id": "generic-2",
                                    "project_path": "/tmp/project-c",
                                    "usage": {
                                        "input_tokens": 1000,
                                        "cached_input_tokens": 100,
                                        "output_tokens": 200,
                                        "reasoning_tokens": 20,
                                        "total_tokens": 1220,
                                    },
                                }
                            ),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                second = adapter.collect(_make_window())

            self.assertEqual(len(second.events), 2)

    def test_collect_chart_uses_day_rollups_but_keeps_boundary_days_exact(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            log_file = root / "generic.jsonl"
            log_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-24T08:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-a",
                                "project_path": "/tmp/project-a",
                                "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-24T18:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-a",
                                "project_path": "/tmp/project-a",
                                "usage": {"input_tokens": 200, "output_tokens": 40, "total_tokens": 240},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-25T10:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-b",
                                "project_path": "/tmp/project-b",
                                "usage": {"input_tokens": 300, "output_tokens": 60, "total_tokens": 360},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T08:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-c",
                                "project_path": "/tmp/project-c",
                                "usage": {"input_tokens": 400, "output_tokens": 80, "total_tokens": 480},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T10:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-c",
                                "project_path": "/tmp/project-c",
                                "usage": {"input_tokens": 500, "output_tokens": 100, "total_tokens": 600},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = GenericOpenAICompatibleAdapter()
                result = adapter.collect_chart(
                    _window(
                        datetime(2026, 3, 24, 12, 0, tzinfo=tzinfo),
                        datetime(2026, 3, 26, 9, 0, tzinfo=tzinfo),
                        label="Custom boundary window",
                    )
                )

            per_day: dict[str, int] = {}
            for event in result.events:
                day = event.timestamp.astimezone(tzinfo).strftime("%Y-%m-%d")
                per_day[day] = per_day.get(day, 0) + event.total_tokens

            self.assertEqual(per_day["2026-03-24"], 240)
            self.assertEqual(per_day["2026-03-25"], 360)
            self.assertEqual(per_day["2026-03-26"], 480)

    def test_collect_chart_reuses_day_rollup_cache_for_full_days(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
            log_file = root / "generic.jsonl"
            log_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-25T11:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-1",
                                "project_path": "/tmp/project-b",
                                "usage": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500},
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T11:00:00-07:00",
                                "provider": "openai-compatible",
                                "model": "deepseek-chat",
                                "session_id": "generic-2",
                                "project_path": "/tmp/project-c",
                                "usage": {"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = GenericOpenAICompatibleAdapter()
                window = _window(
                    datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
                    datetime(2026, 3, 27, 0, 0, tzinfo=tzinfo),
                    label="Two full days",
                )
                first = adapter.collect_chart(window)
                self.assertEqual(len(first.events), 2)
                with patch.object(adapter, "_collect_file", side_effect=AssertionError("chart cache miss")):
                    second = adapter.collect_chart(window)

            self.assertEqual(len(second.events), 2)


if __name__ == "__main__":
    unittest.main()
