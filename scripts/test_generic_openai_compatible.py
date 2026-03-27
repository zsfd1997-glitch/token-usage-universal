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
from core.config import TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
from core.models import TimeWindow


def _make_window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class GenericAdapterTests(unittest.TestCase):
    def test_detect_requires_explicit_glob_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            detection = GenericOpenAICompatibleAdapter().detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn(TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV, detection.summary)

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


if __name__ == "__main__":
    unittest.main()
