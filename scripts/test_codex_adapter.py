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
from core.config import TOKEN_USAGE_CACHE_ROOT_ENV, TOKEN_USAGE_CODEX_ROOT_ENV
from core.models import SourceDetection, TimeWindow


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

    def test_collect_uses_last_token_usage_when_available(self) -> None:
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
                                        "last_token_usage": {
                                            "input_tokens": 100,
                                            "cached_input_tokens": 20,
                                            "output_tokens": 10,
                                            "reasoning_output_tokens": 5,
                                            "total_tokens": 110,
                                        },
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
                                        "last_token_usage": {
                                            "input_tokens": 60,
                                            "cached_input_tokens": 15,
                                            "output_tokens": 20,
                                            "reasoning_output_tokens": 3,
                                            "total_tokens": 80,
                                        },
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
            self.assertEqual(result.events[0].total_tokens, 115)
            self.assertEqual(result.events[1].total_tokens, 83)
            self.assertEqual(result.events[1].input_tokens, 45)
            self.assertEqual(result.events[1].cached_input_tokens, 15)
            self.assertEqual(result.events[1].output_tokens, 20)
            self.assertEqual(result.events[1].reasoning_tokens, 3)
            self.assertEqual(result.events[0].model, "gpt-5.4")
            self.assertEqual(result.events[0].raw_model, "GPT-5.4")
            self.assertEqual(result.events[0].model_resolution, "exact")

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
            self.assertEqual(result.events[1].input_tokens, 40)
            self.assertEqual(result.events[1].cached_input_tokens, 10)
            self.assertEqual(result.events[1].output_tokens, 5)
            self.assertEqual(result.verification_issues, [])

    def test_collect_prefers_top_level_turn_context_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "30" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "sess-ctx",
                                    "timestamp": "2026-03-30T09:55:00-07:00",
                                    "cwd": "/tmp/project-a",
                                    "model_provider": "openai",
                                    "base_instructions": {"text": "You are Codex, a coding agent based on GPT-5."},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "timestamp": "2026-03-30T10:00:00-07:00",
                                "payload": {
                                    "turn_id": "turn-1",
                                    "cwd": "/tmp/project-a",
                                    "model": "gpt-5.4",
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-30T10:01:00-07:00",
                                "payload": {
                                    "type": "token_count",
                                    "model": "GPT-5",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 100,
                                            "cached_input_tokens": 40,
                                            "output_tokens": 20,
                                            "total_tokens": 120,
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
                result = CodexAdapter().collect(
                    TimeWindow(
                        start=datetime(2026, 3, 30, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
                        end=datetime(2026, 3, 30, 23, 59, tzinfo=ZoneInfo("US/Pacific")),
                        label="Today (2026-03-30 PDT)",
                        timezone_name="US/Pacific",
                    )
                )

            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].model, "gpt-5.4")
            self.assertEqual(result.events[0].raw_model, "gpt-5.4")
            self.assertEqual(result.events[0].model_resolution, "exact")

    def test_collect_reuses_incremental_cache_for_unchanged_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
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
                                            "input_tokens": 100,
                                            "cached_input_tokens": 20,
                                            "output_tokens": 10,
                                            "total_tokens": 110,
                                        }
                                    },
                                },
                            }
                        )
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_CODEX_ROOT_ENV: str(root),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = CodexAdapter()
                first = adapter.collect(_make_window())
                self.assertEqual(len(first.events), 1)
                with patch.object(adapter, "_collect_file", side_effect=AssertionError("cache miss")):
                    second = adapter.collect(_make_window())

            self.assertEqual(len(second.events), 1)

    def test_collect_infers_codex_release_model_when_only_generic_gpt5_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "03" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "sess-old",
                                    "timestamp": "2026-03-03T09:55:00-08:00",
                                    "cwd": "/tmp/project-old",
                                    "model_provider": "openai",
                                    "base_instructions": {"text": "You are Codex, a coding agent based on GPT-5."},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "timestamp": "2026-03-03T10:01:00-08:00",
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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                result = CodexAdapter().collect(
                    TimeWindow(
                        start=datetime(2026, 3, 3, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
                        end=datetime(2026, 3, 3, 23, 59, tzinfo=ZoneInfo("US/Pacific")),
                        label="Today (2026-03-03 PST)",
                        timezone_name="US/Pacific",
                    )
                )

            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].model, "gpt-5.3-codex")
            self.assertEqual(result.events[0].raw_model, "GPT-5")
            self.assertEqual(result.events[0].model_resolution, "inferred")

    def test_collect_chart_reuses_day_rollup_cache_for_full_days(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / "cache"
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
                                "timestamp": "2026-03-26T10:00:00-07:00",
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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_CODEX_ROOT_ENV: str(root),
                    TOKEN_USAGE_CACHE_ROOT_ENV: str(cache_root),
                },
                clear=False,
            ):
                adapter = CodexAdapter()
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

    def test_collect_scans_relevant_date_dirs_without_full_tree_walk(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_file = root / "2026" / "03" / "29" / "rollout.jsonl"
            session_file.parent.mkdir(parents=True)
            session_file.write_text(
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-03-30T00:30:00-07:00",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 120,
                                    "cached_input_tokens": 20,
                                    "output_tokens": 15,
                                    "total_tokens": 135,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                adapter = CodexAdapter()
                with patch.object(
                    adapter,
                    "detect",
                    return_value=SourceDetection(
                        source_id=adapter.source_id,
                        display_name=adapter.display_name,
                        provider=adapter.provider,
                        accuracy_level=adapter.accuracy_level,
                        supported=True,
                        available=True,
                        summary="local token_count logs available",
                        candidate_paths=[str(session_file)],
                    ),
                ):
                    with patch("pathlib.Path.rglob", side_effect=AssertionError("full scan not expected")):
                        result = adapter.collect(
                            _window(
                                datetime(2026, 3, 30, 0, 0, tzinfo=tzinfo),
                                datetime(2026, 3, 30, 23, 59, tzinfo=tzinfo),
                                label="Today (2026-03-30 PDT)",
                        )
                    )

            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].total_tokens, 135)


if __name__ == "__main__":
    unittest.main()
