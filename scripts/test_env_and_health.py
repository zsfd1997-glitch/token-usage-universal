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
    TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
    TOKEN_USAGE_CODEX_ROOT_ENV,
    TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV,
    TOKEN_USAGE_OPENCODE_BIN_ENV,
    TOKEN_USAGE_OPENCODE_ROOTS_ENV,
    TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV,
    TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV,
    default_claude_local_agent_root,
    default_cache_root,
    default_desktop_app_roots,
    default_minimax_agent_root,
    default_opencode_roots,
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

    def test_codex_env_override_expands_windows_style_percent_variable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "USERPROFILE": "C:/Users/tester",
                TOKEN_USAGE_CODEX_ROOT_ENV: "%USERPROFILE%/.codex/sessions",
            },
            clear=False,
        ):
            adapter = CodexAdapter()

        self.assertEqual(adapter.root, Path("C:/Users/tester/.codex/sessions"))

    def test_windows_default_claude_local_agent_root_prefers_appdata(self) -> None:
        path = default_claude_local_agent_root(
            os_name="nt",
            home=Path("/unused"),
            appdata="C:/Users/tester/AppData/Roaming",
        )

        self.assertEqual(path, Path("C:/Users/tester/AppData/Roaming/Claude/local-agent-mode-sessions"))

    def test_default_cache_root_is_not_tied_to_codex(self) -> None:
        path = default_cache_root(
            os_name="nt",
            home=Path("/unused"),
            localappdata="C:/Users/tester/AppData/Local",
        )

        self.assertEqual(path, Path("C:/Users/tester/AppData/Local/token-usage-universal/cache"))

    def test_windows_default_minimax_agent_root_prefers_appdata(self) -> None:
        path = default_minimax_agent_root(
            os_name="nt",
            home=Path("/unused"),
            appdata="C:/Users/tester/AppData/Roaming",
        )

        self.assertEqual(path, Path("C:/Users/tester/AppData/Roaming/MiniMax Agent"))

    def test_default_desktop_app_roots_cover_mac_and_windows(self) -> None:
        mac_roots = default_desktop_app_roots(
            ("Kimi", "Moonshot"),
            os_name="posix",
            home=Path("/Users/tester"),
            platform_name="darwin",
        )
        windows_roots = default_desktop_app_roots(
            ("Perplexity",),
            os_name="nt",
            home=Path("/unused"),
            appdata="C:/Users/tester/AppData/Roaming",
            localappdata="C:/Users/tester/AppData/Local",
        )

        self.assertIn(Path("/Users/tester/Library/Application Support/Kimi"), mac_roots)
        self.assertIn(Path("/Users/tester/Library/Application Support/Moonshot"), mac_roots)
        self.assertIn(Path("C:/Users/tester/AppData/Roaming/Perplexity"), windows_roots)
        self.assertIn(Path("C:/Users/tester/AppData/Local/Perplexity"), windows_roots)

    def test_windows_default_opencode_roots_include_roaming_and_local(self) -> None:
        roots = default_opencode_roots(
            os_name="nt",
            home=Path("/unused"),
            appdata="C:/Users/tester/AppData/Roaming",
            localappdata="C:/Users/tester/AppData/Local",
        )

        self.assertIn(Path("C:/Users/tester/AppData/Roaming/OpenCode"), roots)
        self.assertIn(Path("C:/Users/tester/AppData/Local/opencode"), roots)


class HealthReportTests(unittest.TestCase):
    def test_health_report_marks_partial_and_includes_next_steps(self) -> None:
        report = build_health_report(
            [
                _result("codex", available=True, summary="ready"),
                _result("claude-code", available=False, summary="missing timing"),
                _result("claude-desktop", available=False, summary="missing desktop cache payload"),
                _result("opencode", available=False, summary="missing cli"),
                _result("minimax-agent", available=False, summary="missing cache payload"),
                _result("kimi-desktop", available=False, summary="missing desktop payload"),
                _result("glm-desktop", available=False, summary="missing desktop payload"),
                _result("qwen-desktop", available=False, summary="missing desktop payload"),
                _result("doubao-desktop", available=False, summary="missing desktop payload"),
                _result("perplexity-desktop", available=False, summary="missing desktop payload"),
                _result("generic-openai-compatible", available=False, summary="set env"),
            ]
        )

        self.assertEqual(report["overall_status"], "partial")
        self.assertEqual(report["ready_sources"], 1)
        self.assertGreaterEqual(len(report["next_steps"]), 3)
        self.assertIn("local-agent-mode-sessions", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_CLAUDE_DESKTOP_ROOT", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_OPENCODE_BIN", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_OPENCODE_ROOTS", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_MINIMAX_AGENT_ROOT", " ".join(report["next_steps"]))
        self.assertIn(TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV, " ".join(report["next_steps"]))
        self.assertIn(TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV, " ".join(report["next_steps"]))
        self.assertIn(TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV, " ".join(report["next_steps"]))
        self.assertIn(TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV, " ".join(report["next_steps"]))
        self.assertIn(TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV, " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_GENERIC_LOG_GLOBS", " ".join(report["next_steps"]))
        self.assertIn("TOKEN_USAGE_DISCOVERY_ROOTS", " ".join(report["next_steps"]))
        self.assertEqual(
            report["recommended_commands"][0],
            "python3 scripts/token_usage.py health",
        )


if __name__ == "__main__":
    unittest.main()
