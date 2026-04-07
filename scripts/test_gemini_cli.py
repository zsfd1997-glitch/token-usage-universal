from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.gemini_cli import GeminiCliAdapter
from core.models import TimeWindow


def _window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class GeminiCliAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_from_session_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "tmp" / "token-usage-universal"
            chats_dir = project_dir / "chats"
            chats_dir.mkdir(parents=True)
            project_dir.joinpath(".project_root").write_text("/tmp/gemini-demo\n", encoding="utf-8")
            chats_dir.joinpath("session-2026-03-25T10-00-abcd1234.json").write_text(
                json.dumps(
                    {
                        "sessionId": "gemini-session-1",
                        "projectHash": "token-usage-universal",
                        "startTime": "2026-03-25T10:00:00-07:00",
                        "lastUpdated": "2026-03-25T10:01:00-07:00",
                        "messages": [
                            {
                                "id": "user-1",
                                "timestamp": "2026-03-25T10:00:00-07:00",
                                "type": "user",
                                "content": "hello",
                            },
                            {
                                "id": "gemini-1",
                                "timestamp": "2026-03-25T10:01:00-07:00",
                                "type": "gemini",
                                "model": "gemini-2.5-pro",
                                "tokens": {
                                    "input": 100,
                                    "cached": 20,
                                    "output": 30,
                                    "thoughts": 5,
                                    "tool": 7,
                                    "total": 142,
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            adapter = GeminiCliAdapter(root=root)
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.session_id, "gemini-session-1")
        self.assertEqual(event.project_path, "/tmp/gemini-demo")
        self.assertEqual(event.input_tokens, 107)
        self.assertEqual(event.cached_input_tokens, 20)
        self.assertEqual(event.output_tokens, 30)
        self.assertEqual(event.reasoning_tokens, 5)
        self.assertEqual(event.total_tokens, 142)

    def test_detect_reports_session_files_without_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chats_dir = root / "tmp" / "demo-project" / "chats"
            chats_dir.mkdir(parents=True)
            chats_dir.joinpath("session-2026-03-25T11-00-abcd1234.json").write_text(
                json.dumps(
                    {
                        "sessionId": "gemini-session-2",
                        "startTime": "2026-03-25T11:00:00-07:00",
                        "lastUpdated": "2026-03-25T11:01:00-07:00",
                        "messages": [
                            {
                                "id": "gemini-2",
                                "timestamp": "2026-03-25T11:01:00-07:00",
                                "type": "gemini",
                                "model": "gemini-2.5-flash",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            detection = GeminiCliAdapter(root=root).detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact token-bearing assistant messages", detection.summary)


if __name__ == "__main__":
    unittest.main()
