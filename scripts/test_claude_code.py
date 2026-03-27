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

from adapters.claude_code import ClaudeCodeAdapter
from core.models import TimeWindow


def _make_window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class ClaudeCodeAdapterTests(unittest.TestCase):
    def test_detect_transcript_only_reports_missing_timing_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_root = root / "transcripts"
            transcript_root.mkdir(parents=True)
            (transcript_root / "sample.jsonl").write_text(
                json.dumps({"type": "user", "timestamp": "2026-03-25T12:00:00Z", "content": "hello"}) + "\n",
                encoding="utf-8",
            )

            adapter = ClaudeCodeAdapter(
                transcript_root=transcript_root,
                local_agent_root=root / "local-agent-mode-sessions",
            )
            detection = adapter.detect()

            self.assertTrue(detection.supported)
            self.assertFalse(detection.available)
            self.assertEqual(detection.status, "not-found")
            self.assertIn("no timing.json captured", detection.summary)
            self.assertIn("text-only", " ".join(detection.details))

    def test_collect_uses_timing_json_exact_total_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timing_file = root / "local-agent-mode-sessions" / "run-1" / "timing.json"
            timing_file.parent.mkdir(parents=True)
            timing_file.write_text(
                json.dumps(
                    {
                        "total_tokens": 84_852,
                        "duration_ms": 23_332,
                        "executor_end": "2026-03-25T18:32:45Z",
                    }
                ),
                encoding="utf-8",
            )

            adapter = ClaudeCodeAdapter(
                transcript_root=root / "transcripts",
                local_agent_root=root / "local-agent-mode-sessions",
            )
            result = adapter.collect(_make_window())

            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].total_tokens, 84_852)
            self.assertIsNone(result.events[0].input_tokens)
            self.assertEqual(result.events[0].session_id, "run-1")
            self.assertIn("only provides total_tokens", " ".join(result.verification_issues))

    def test_collect_rejects_timing_json_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timing_file = root / "local-agent-mode-sessions" / "run-2" / "timing.json"
            timing_file.parent.mkdir(parents=True)
            timing_file.write_text(
                json.dumps(
                    {
                        "duration_ms": 23_332,
                        "executor_end": "2026-03-25T18:32:45Z",
                    }
                ),
                encoding="utf-8",
            )

            adapter = ClaudeCodeAdapter(
                transcript_root=root / "transcripts",
                local_agent_root=root / "local-agent-mode-sessions",
            )
            result = adapter.collect(_make_window())

            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(result.events, [])
            self.assertIn("missing total_tokens or executor_end", " ".join(result.verification_issues))


if __name__ == "__main__":
    unittest.main()
