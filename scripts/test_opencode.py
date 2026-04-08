from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.opencode import OpenCodeAdapter
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


class OpenCodeAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_via_local_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "storage" / "session" / "global"
            message_dir = root / "storage" / "message" / "ses_local"
            completed_at = int(datetime(2026, 3, 25, 12, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
            created_at = int(datetime(2026, 3, 25, 11, 59, tzinfo=PACIFIC_TZ).timestamp() * 1000)
            session_dir.mkdir(parents=True)
            message_dir.mkdir(parents=True)

            (session_dir / "ses_local.json").write_text(
                json.dumps(
                    {
                        "id": "ses_local",
                        "projectID": "global",
                        "directory": "/tmp/local-demo",
                        "time": {"created": created_at, "updated": completed_at},
                    }
                ),
                encoding="utf-8",
            )
            (root / "storage" / "project").mkdir(parents=True)
            (root / "storage" / "project" / "global.json").write_text(
                json.dumps({"id": "global", "worktree": "/tmp/local-demo"}),
                encoding="utf-8",
            )
            (message_dir / "msg_local.json").write_text(
                json.dumps(
                    {
                        "id": "msg_local",
                        "sessionID": "ses_local",
                        "role": "assistant",
                        "time": {"created": created_at, "completed": completed_at},
                        "modelID": "minimax-m2.1-free",
                        "providerID": "opencode",
                        "path": {"cwd": "/tmp/local-demo", "root": "/tmp/local-demo"},
                        "tokens": {
                            "input": 200,
                            "output": 50,
                            "reasoning": 3,
                            "cache": {"read": 40, "write": 10},
                        },
                    }
                ),
                encoding="utf-8",
            )

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            with patch.object(adapter, "_resolve_cli", return_value=None):
                detection = adapter.detect()
                result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.summary, "OpenCode local storage produced exact token usage records")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].provider, "opencode")
        self.assertEqual(result.events[0].project_path, "/tmp/local-demo")
        self.assertEqual(result.events[0].input_tokens, 210)
        self.assertEqual(result.events[0].cached_input_tokens, 40)
        self.assertEqual(result.events[0].output_tokens, 50)
        self.assertEqual(result.events[0].reasoning_tokens, 3)
        self.assertEqual(result.events[0].total_tokens, 303)
        self.assertEqual(result.events[0].raw_event_kind, "opencode_local:message_json")

    def test_detect_and_collect_exact_usage_via_cli_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            def fake_run(*args, timeout: int):
                if args == ("session", "list", "--max-count", "8", "--format", "json"):
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps([{"id": "ses_1", "updated_at": "2026-03-25T12:00:00-07:00", "title": "demo"}]),
                        stderr="",
                    )
                if args == ("export", "ses_1"):
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps(
                            {
                                "id": "ses_1",
                                "project": "/tmp/demo",
                                "messages": [
                                    {
                                        "created_at": "2026-03-25T12:00:00-07:00",
                                        "model": "moonshot/kimi-k2",
                                        "usage": {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250},
                                    }
                                ],
                            }
                        ),
                        stderr="",
                    )
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode"), patch.object(
                adapter,
                "_run_cli",
                side_effect=fake_run,
            ):
                detection = adapter.detect()
                result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].provider, "moonshot")
        self.assertEqual(result.events[0].total_tokens, 250)
        self.assertEqual(result.events[0].session_id, "ses_1")

    def test_detect_reports_local_data_when_cli_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")
            (root / "prompt-history.jsonl").write_text("{}", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            with patch.object(adapter, "_resolve_cli", return_value=None):
                detection = adapter.detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact token-bearing assistant message JSON or CLI export", detection.summary)


if __name__ == "__main__":
    unittest.main()
