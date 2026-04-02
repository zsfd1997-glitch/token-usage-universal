from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CLI_PATH = SCRIPT_DIR / "token_usage.py"


class CliIntegrationTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        log_file = root / "generic.jsonl"
        log_file.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-03-24T09:00:00-07:00",
                            "provider": "openai-compatible",
                            "model": "qwen-max",
                            "session_id": "cli-1",
                            "project_path": "/tmp/project-cli",
                            "usage": {
                                "input_tokens": 900,
                                "cached_input_tokens": 100,
                                "output_tokens": 180,
                                "reasoning_tokens": 20,
                                "total_tokens": 1100,
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-03-25T09:00:00-07:00",
                            "provider": "openai-compatible",
                            "model": "glm-4.5",
                            "session_id": "cli-2",
                            "project_path": "/tmp/project-cli",
                            "usage": {
                                "input_tokens": 1000,
                                "cached_input_tokens": 200,
                                "output_tokens": 220,
                                "reasoning_tokens": 30,
                                "total_tokens": 1250,
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return log_file

    def test_report_json_works_with_generic_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)

            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            env["TOKEN_USAGE_CODEX_ROOT"] = str(root / "unused-codex")
            env["TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT"] = str(root / "unused-claude-transcripts")
            env["TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT"] = str(root / "unused-claude-local-agent")
            env["TOKEN_USAGE_OPENCODE_ROOTS"] = str(root / "unused-opencode")
            env["TOKEN_USAGE_OPENCODE_BIN"] = str(root / "missing-opencode")
            env["TOKEN_USAGE_MINIMAX_AGENT_ROOT"] = str(root / "unused-minimax")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["summary"]["total_tokens"], 2350)
            self.assertEqual(payload["report"]["summary"]["effective_tokens"], 2050)
            self.assertEqual(payload["report"]["summary"]["cost_accuracy"], "estimated")
            self.assertIsNotNone(payload["report"]["current_session"])

    def test_report_default_sources_do_not_double_count_generic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)

            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            env["TOKEN_USAGE_CODEX_ROOT"] = str(root / "unused-codex")
            env["TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT"] = str(root / "unused-claude-transcripts")
            env["TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT"] = str(root / "unused-claude-local-agent")
            env["TOKEN_USAGE_OPENCODE_ROOTS"] = str(root / "unused-opencode")
            env["TOKEN_USAGE_OPENCODE_BIN"] = str(root / "missing-opencode")
            env["TOKEN_USAGE_MINIMAX_AGENT_ROOT"] = str(root / "unused-minimax")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["summary"]["total_tokens"], 2350)

    def test_report_by_day_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--source",
                    "generic-openai-compatible",
                    "--by",
                    "day",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual([row["date"] for row in payload["report"]["by_day"]], ["2026-03-24", "2026-03-25"])

    def test_report_trend_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--trend",
                    "7d",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["charts"]["trend_7d"]["days"], 7)

    def test_report_calendar_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--calendar",
                    "month",
                    "--month",
                    "2026-03",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["charts"]["calendar_month"]["month"], "2026-03")

    def test_report_current_session_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--current-session",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["current_session"]["session_id"], "cli-2")

    def test_report_dashboard_ascii_includes_trend_and_calendar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--dashboard",
                    "today",
                    "--source",
                    "generic-openai-compatible",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertIn("按模型", result.stdout)
            self.assertIn("按项目", result.stdout)
            self.assertIn("最近 7 天", result.stdout)
            self.assertIn("本月分布 2026-03", result.stdout)
            self.assertIn("去缓存后", result.stdout)
            self.assertIn("合计", result.stdout)
            self.assertIn("均值", result.stdout)
            self.assertIn("最高", result.stdout)
            self.assertGreaterEqual(
                sum(1 for line in result.stdout.splitlines() if "合计" in line and "估算 $" in line),
                2,
            )
            self.assertNotIn("最新", result.stdout)
            self.assertNotIn("按去缓存后 token", result.stdout)
            self.assertNotIn("诊断 / 缺失来源", result.stdout)

    def test_report_session_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = self._write_fixture(root)
            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            env["TOKEN_USAGE_DISCOVERY_ROOTS"] = str(root / "unused")
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--session",
                    "cli-1",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["session_detail"]["session_id"], "cli-1")

    def test_health_json_includes_all_supported_sources(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "health", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        source_ids = [item["source_id"] for item in payload["sources"]]
        self.assertEqual(len(source_ids), 35)
        self.assertIn("codex", source_ids)
        self.assertIn("claude-code", source_ids)
        self.assertIn("claude-desktop", source_ids)
        self.assertIn("opencode", source_ids)
        self.assertIn("minimax-agent", source_ids)
        self.assertIn("kimi-desktop", source_ids)
        self.assertIn("glm-desktop", source_ids)
        self.assertIn("qwen-desktop", source_ids)
        self.assertIn("doubao-desktop", source_ids)
        self.assertIn("perplexity-desktop", source_ids)
        self.assertIn("openai-api", source_ids)
        self.assertIn("anthropic-api", source_ids)
        self.assertIn("moonshot-kimi-api", source_ids)
        self.assertIn("zhipu-glm-api", source_ids)
        self.assertIn("qwen-api", source_ids)
        self.assertIn("sensenova-api", source_ids)
        self.assertIn("baichuan-api", source_ids)
        self.assertIn("siliconflow-api", source_ids)
        self.assertIn("spark-api", source_ids)
        self.assertIn("generic-openai-compatible", source_ids)
        self.assertIn("overall_status", payload)

    def test_explore_requires_tty(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "explore"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interactive TTY", result.stderr or result.stdout)

    def test_targets_json_exposes_frozen_registry(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "targets", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total_ecosystems"], 20)
        self.assertEqual(payload["summary"]["china_priority_ecosystems"], 13)
        self.assertEqual(payload["scope"]["surfaces"], ["desktop", "cli", "ide"])


if __name__ == "__main__":
    unittest.main()
