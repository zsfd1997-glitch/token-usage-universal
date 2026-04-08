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
    def test_collect_uses_project_jsonl_usage_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_file = root / ".claude" / "projects" / "-Users-example-project" / "session-1.jsonl"
            project_file.parent.mkdir(parents=True)
            project_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "timestamp": "2026-03-25T12:00:00Z",
                                "sessionId": "session-1",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "timestamp": "2026-03-25T12:01:00Z",
                                "sessionId": "session-1",
                                "cwd": "/tmp/example-project",
                                "message": {
                                    "role": "assistant",
                                    "model": "claude-haiku-4-5-20251001",
                                    "usage": {
                                        "input_tokens": 10,
                                        "cache_creation_input_tokens": 30099,
                                        "cache_read_input_tokens": 123,
                                        "output_tokens": 616,
                                    },
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            adapter = ClaudeCodeAdapter(
                transcript_root=root / ".claude" / "transcripts",
                local_agent_root=root / "local-agent-mode-sessions",
            )
            detection = adapter.detect()
            result = adapter.collect(_make_window())

            self.assertTrue(detection.available)
            self.assertIn("project JSONL", detection.summary)
            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].model, "claude-haiku-4-5-20251001")
            self.assertEqual(result.events[0].input_tokens, 30109)
            self.assertEqual(result.events[0].cached_input_tokens, 123)
            self.assertEqual(result.events[0].output_tokens, 616)
            self.assertEqual(result.events[0].total_tokens, 30848)
            self.assertEqual(result.events[0].project_path, "/tmp/example-project")
            self.assertEqual(result.events[0].raw_event_kind, "session-1.jsonl:assistant_usage")

    def test_detect_transcript_only_reports_missing_exact_json(self) -> None:
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
            self.assertIn("no exact Claude usage payload", detection.summary)
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
            self.assertIn("missing total_tokens or executor_end/grader_end", " ".join(result.verification_issues))

    def test_collect_uses_equivalent_exact_json_not_named_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exact_file = root / "local-agent-mode-sessions" / "run-3" / "session-summary.json"
            exact_file.parent.mkdir(parents=True)
            exact_file.write_text(
                json.dumps(
                    {
                        "total_tokens": 12_345,
                        "grader_end": "2026-03-25T18:32:45Z",
                    }
                ),
                encoding="utf-8",
            )

            adapter = ClaudeCodeAdapter(
                transcript_root=root / "transcripts",
                local_agent_root=root / "local-agent-mode-sessions",
            )
            detection = adapter.detect()
            result = adapter.collect(_make_window())

            self.assertTrue(detection.available)
            self.assertIn("exact JSON", detection.summary)
            self.assertEqual(result.scanned_files, 1)
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].total_tokens, 12_345)
            self.assertEqual(result.events[0].raw_event_kind, "session-summary.json:session_total")

    def test_detect_new_layout_without_exact_json_reports_layout_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_root = root / "transcripts"
            transcript_root.mkdir(parents=True)
            (transcript_root / "sample.jsonl").write_text(
                json.dumps({"type": "user", "timestamp": "2026-03-25T12:00:00Z", "content": "hello"}) + "\n",
                encoding="utf-8",
            )
            session_root = root / "local-agent-mode-sessions" / "run-4"
            session_root.mkdir(parents=True)
            (session_root / ".claude.json").write_text(json.dumps({"firstStartTime": "2026-03-25T12:00:00Z"}), encoding="utf-8")
            (session_root / "cowork_settings.json").write_text("{}", encoding="utf-8")

            adapter = ClaudeCodeAdapter(
                transcript_root=transcript_root,
                local_agent_root=root / "local-agent-mode-sessions",
            )
            detection = adapter.detect()
            result = adapter.collect(_make_window())

            self.assertFalse(detection.available)
            self.assertIn("local-agent layout detected", detection.summary)
            self.assertIn(".claude.json", " ".join(detection.details))
            self.assertIn("total_tokens and executor_end/grader_end", " ".join(detection.details))
            self.assertEqual(result.scanned_files, 2)
            self.assertIn("none exposed total_tokens", " ".join(result.verification_issues))


if __name__ == "__main__":
    unittest.main()
