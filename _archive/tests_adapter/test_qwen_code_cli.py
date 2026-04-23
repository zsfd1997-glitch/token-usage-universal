from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.qwen_code_cli import QwenCodeCliAdapter
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


class QwenCodeCliAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_from_session_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chats_dir = root / "projects" / "demo-project" / "chats"
            chats_dir.mkdir(parents=True)
            session_file = chats_dir / "session-qwen-1.jsonl"
            session_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "sessionId": "session-qwen-1",
                                "timestamp": "2026-03-25T10:00:00-07:00",
                                "type": "user",
                                "cwd": "/tmp/qwen-demo",
                            }
                        ),
                        json.dumps(
                            {
                                "sessionId": "session-qwen-1",
                                "timestamp": "2026-03-25T10:01:00-07:00",
                                "type": "assistant",
                                "cwd": "/tmp/qwen-demo",
                                "model": "qwen3-coder-plus",
                                "usageMetadata": {
                                    "promptTokenCount": 100,
                                    "candidatesTokenCount": 30,
                                    "cachedContentTokenCount": 20,
                                    "thoughtsTokenCount": 5,
                                    "totalTokenCount": 135,
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            adapter = QwenCodeCliAdapter(root=root)
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.session_id, "session-qwen-1")
        self.assertEqual(event.project_path, "/tmp/qwen-demo")
        self.assertEqual(event.input_tokens, 100)
        self.assertEqual(event.cached_input_tokens, 20)
        self.assertEqual(event.output_tokens, 30)
        self.assertEqual(event.reasoning_tokens, 5)
        self.assertEqual(event.total_tokens, 135)

    def test_detect_reports_session_files_without_usage_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chats_dir = root / "tmp" / "project-hash" / "chats"
            chats_dir.mkdir(parents=True)
            chats_dir.joinpath("session-qwen-2.jsonl").write_text(
                json.dumps(
                    {
                        "sessionId": "session-qwen-2",
                        "timestamp": "2026-03-25T11:00:00-07:00",
                        "type": "assistant",
                        "cwd": "/tmp/qwen-demo",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            detection = QwenCodeCliAdapter(root=root).detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact usageMetadata records", detection.summary)


if __name__ == "__main__":
    unittest.main()
