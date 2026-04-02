from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from hashlib import md5
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.kimi_cli import KimiCliAdapter
from core.models import TimeWindow


def _window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class KimiCliAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_from_wire_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_path = "/tmp/kimi-demo"
            project_hash = md5(project_path.encode("utf-8")).hexdigest()
            session_dir = root / "sessions" / project_hash / "kimi-session-1"
            session_dir.mkdir(parents=True)
            (root / "kimi.json").write_text(
                json.dumps(
                    {
                        "work_dirs": [
                            {
                                "path": project_path,
                                "kaos": "local",
                                "last_session_id": "kimi-session-1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            session_dir.joinpath("wire.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "metadata", "protocol_version": "1.0"}),
                        json.dumps(
                            {
                                "timestamp": datetime(2026, 3, 25, 12, 0, tzinfo=ZoneInfo("US/Pacific")).timestamp(),
                                "message": {
                                    "type": "StatusUpdate",
                                    "payload": {
                                        "message_id": "msg-1",
                                        "token_usage": {
                                            "input_other": 500,
                                            "input_cache_read": 120,
                                            "input_cache_creation": 30,
                                            "output": 80,
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

            adapter = KimiCliAdapter(root=root)
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.session_id, "kimi-session-1")
        self.assertEqual(event.project_path, project_path)
        self.assertEqual(event.input_tokens, 650)
        self.assertEqual(event.cached_input_tokens, 120)
        self.assertEqual(event.output_tokens, 80)
        self.assertEqual(event.total_tokens, 730)

    def test_collect_unwraps_subagent_status_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_path = "/tmp/kimi-demo"
            project_hash = md5(project_path.encode("utf-8")).hexdigest()
            session_dir = root / "sessions" / project_hash / "kimi-session-2"
            session_dir.mkdir(parents=True)
            session_dir.joinpath("wire.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "metadata", "protocol_version": "1.0"}),
                        json.dumps(
                            {
                                "timestamp": datetime(2026, 3, 25, 13, 0, tzinfo=ZoneInfo("US/Pacific")).timestamp(),
                                "message": {
                                    "type": "SubagentEvent",
                                    "payload": {
                                        "event": {
                                            "type": "StatusUpdate",
                                            "payload": {
                                                "message_id": "msg-2",
                                                "token_usage": {
                                                    "input_other": 100,
                                                    "input_cache_read": 10,
                                                    "input_cache_creation": 0,
                                                    "output": 20,
                                                },
                                            },
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

            result = KimiCliAdapter(root=root).collect(_window())

        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].total_tokens, 130)

    def test_detect_reports_wire_files_without_token_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "sessions" / "hash" / "kimi-session-3"
            session_dir.mkdir(parents=True)
            session_dir.joinpath("wire.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "metadata", "protocol_version": "1.0"}),
                        json.dumps(
                            {
                                "timestamp": datetime(2026, 3, 25, 14, 0, tzinfo=ZoneInfo("US/Pacific")).timestamp(),
                                "message": {"type": "TurnBegin", "payload": {"user_input": "hi"}},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            detection = KimiCliAdapter(root=root).detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact token_usage records", detection.summary)


if __name__ == "__main__":
    unittest.main()
