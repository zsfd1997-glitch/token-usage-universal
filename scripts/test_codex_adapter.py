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

from adapters.codex import CodexAdapter
from core.config import TOKEN_USAGE_CODEX_ROOT_ENV
from core.models import TimeWindow


def _make_window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class CodexAdapterTests(unittest.TestCase):
    def test_detect_uses_env_override_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "25" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                detection = CodexAdapter().detect()

            self.assertTrue(detection.available)
            self.assertEqual(detection.status, "ready")
            self.assertIn(str(session_file), detection.candidate_paths[0])

    def test_collect_turns_cumulative_totals_into_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "25" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "sess-1",
                                    "cwd": "/tmp/project-a",
                                    "model_provider": "openai",
                                    "base_instructions": {"text": "Run with GPT-5.4"},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-25T10:00:00-07:00",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 100,
                                            "cached_input_tokens": 20,
                                            "output_tokens": 10,
                                            "total_tokens": 110,
                                        }
                                    },
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-25T10:05:00-07:00",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 160,
                                            "cached_input_tokens": 40,
                                            "output_tokens": 30,
                                            "total_tokens": 190,
                                        }
                                    },
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                result = CodexAdapter().collect(_make_window())

            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(len(result.events), 2)
            self.assertEqual(result.events[0].total_tokens, 110)
            self.assertEqual(result.events[1].total_tokens, 80)
            self.assertEqual(result.events[1].input_tokens, 60)
            self.assertEqual(result.events[1].cached_input_tokens, 20)
            self.assertEqual(result.events[1].output_tokens, 20)
            self.assertEqual(result.events[0].model, "GPT-5.4")

    def test_collect_falls_back_to_last_token_usage_on_negative_total_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "25" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-25T10:00:00-07:00",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 200,
                                            "cached_input_tokens": 40,
                                            "output_tokens": 20,
                                            "total_tokens": 220,
                                        }
                                    },
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-25T10:06:00-07:00",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 10,
                                            "cached_input_tokens": 2,
                                            "output_tokens": 1,
                                            "total_tokens": 11,
                                        },
                                        "last_token_usage": {
                                            "input_tokens": 50,
                                            "cached_input_tokens": 10,
                                            "output_tokens": 5,
                                            "total_tokens": 55,
                                        },
                                    },
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                result = CodexAdapter().collect(_make_window())

            self.assertEqual(len(result.events), 2)
            self.assertEqual(result.events[1].total_tokens, 55)
            self.assertIn("fallback to last_token_usage", " ".join(result.verification_issues))


if __name__ == "__main__":
    unittest.main()
