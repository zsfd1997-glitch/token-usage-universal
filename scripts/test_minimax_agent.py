from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.minimax_agent import MiniMaxAgentAdapter
from core.models import TimeWindow
from test_time import PACIFIC_TZ


def _window() -> TimeWindow:
    tzinfo = PACIFIC_TZ
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


def _cache_blob(url: str, payload: object) -> bytes:
    return (b"\x00" * 28) + f"1/0/{url}".encode("utf-8") + b"\x00" + gzip.compress(json.dumps(payload).encode("utf-8"))


class MiniMaxAgentAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_file = cache_dir / "deadbeef_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://agent.minimax.io/api/v1/chat/completions",
                    {
                        "created_at": "2026-03-25T12:00:00-07:00",
                        "provider": "minimax",
                        "model": "MiniMax-M1",
                        "conversation_id": "mm-1",
                        "usage": {"prompt_tokens": 500, "completion_tokens": 120, "total_tokens": 620},
                    },
                )
            )

            adapter = MiniMaxAgentAdapter(root=root)
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "mm-1")
        self.assertEqual(result.events[0].total_tokens, 620)

    def test_detect_reports_cache_without_exact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_dir.joinpath("feedface_0").write_bytes(
                _cache_blob(
                    "https://agent.minimax.io/api/v1/user/info",
                    {"requestID": "req-1", "user": {"id": "u-1"}},
                )
            )

            detection = MiniMaxAgentAdapter(root=root).detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact token payloads", detection.summary)


if __name__ == "__main__":
    unittest.main()
