from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.claude_code import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from core.config import (
    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
    TOKEN_USAGE_CODEX_ROOT_ENV,
)
from core.health import build_health_report
from core.models import SourceCollectResult, SourceDetection


def _result(source_id: str, *, available: bool, summary: str) -> SourceCollectResult:
    return SourceCollectResult(
        detection=SourceDetection(
            source_id=source_id,
            display_name=source_id,
            provider="test",
            accuracy_level="exact",
            supported=True,
            available=available,
            summary=summary,
        )
    )


class EnvironmentOverrideTests(unittest.TestCase):
    def test_codex_adapter_uses_env_override_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "2026" / "03" / "26" / "rollout.jsonl"
            sample.parent.mkdir(parents=True)
            sample.write_text(
                json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {TOKEN_USAGE_CODEX_ROOT_ENV: str(root)}, clear=False):
                detection = CodexAdapter().detect()

            self.assertTrue(detection.available)
            self.assertEqual(detection.status, "ready")
            self.assertIn(str(sample), detection.candidate_paths[0])

    def test_claude_adapter_uses_env_override_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript_root = root / "transcripts"
            local_agent_root = root / "local-agent-mode-sessions"
            transcript_root.mkdir(parents=True)
            local_agent_root.mkdir(parents=True)
            (transcript_root / "sample.jsonl").write_text(
                json.dumps({"type": "user", "content": "hello"}) + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV: str(transcript_root),
                    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV: str(local_agent_root),
                },
                clear=False,
            ):
                detection = ClaudeCodeAdapter().detect()

            self.assertFalse(detection.available)
            self.assertIn(TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV, detection.summary)


class HealthReportTests(unittest.TestCase):
    def test_health_report_marks_partial_and_includes_next_steps(self) -> None:
        report = build_health_report(
            [
                _result("codex", available=True, summary="ready"),
                _result("claude-code", available=False, summary="missing timing"),
                _result("generic-openai-compatible", available=False, summary="set env"),
            ]
        )

        self.assertEqual(report["overall_status"], "partial")
        self.assertEqual(report["ready_sources"], 1)
        self.assertGreaterEqual(len(report["next_steps"]), 3)
        self.assertIn("TOKEN_USAGE_GENERIC_LOG_GLOBS", " ".join(report["next_steps"]))


if __name__ == "__main__":
    unittest.main()
