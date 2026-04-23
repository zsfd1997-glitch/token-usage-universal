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
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class CliIntegrationTests(unittest.TestCase):
    def _run_cli(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        # Test subprocesses must not read the dev host's persistent
        # environment cache (~/Library/Caches/token-usage-universal/
        # environment.json on macOS, etc.) — that cache filters adapters
        # based on what's installed on the developer's machine, which
        # makes tests non-deterministic. Force the full registry unless
        # the individual test explicitly opts out.
        if env is not None and "TOKEN_USAGE_ALL_SOURCES" not in env:
            env = {**env, "TOKEN_USAGE_ALL_SOURCES": "1"}
        elif env is None:
            env = {**os.environ, "TOKEN_USAGE_ALL_SOURCES": "1"}
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="strict",
            env=env,
        )
        if check and result.returncode != 0:
            self.fail(
                "CLI command failed with non-zero exit status:\n"
                f"args={result.args}\n"
                f"returncode={result.returncode}\n"
                f"stdout={result.stdout}\n"
                f"stderr={result.stderr}"
            )
        return result

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
            result = self._run_cli(
                [
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
            result = self._run_cli(
                [
                    "report",
                    "--start",
                    "2026-03-24T00:00:00-07:00",
                    "--end",
                    "2026-03-25T23:59:00-07:00",
                    "--format",
                    "json",
                ],
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
            result = self._run_cli(
                [
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
            result = self._run_cli(
                [
                    "report",
                    "--trend",
                    "7d",
                    "--source",
                    "generic-openai-compatible",
                    "--format",
                    "json",
                ],
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
            result = self._run_cli(
                [
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
            result = self._run_cli(
                [
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
            result = self._run_cli(
                [
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
            result = self._run_cli(
                [
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
                env=env,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["report"]["session_detail"]["session_id"], "cli-1")

    def test_health_json_includes_all_supported_sources(self) -> None:
        result = self._run_cli(["health", "--format", "json"], env=os.environ.copy())

        payload = json.loads(result.stdout)
        source_ids = [item["source_id"] for item in payload["sources"]]
        # v1.2 slim: opencode + trae + generic-openai-compatible only.
        # Per-provider and per-foreign-client adapters were archived since
        # the deployment routes all traffic through 百炼's compatible URL.
        self.assertEqual(set(source_ids), {"opencode", "trae", "generic-openai-compatible"})
        self.assertIn("overall_status", payload)

    def test_explore_requires_tty(self) -> None:
        result = self._run_cli(["explore"], check=False, env=os.environ.copy())

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interactive TTY", result.stderr or result.stdout)

    def test_health_json_survives_legacy_stdout_encoding(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"
        result = self._run_cli(["health", "--format", "json"], env=env)

        payload = json.loads(result.stdout)
        self.assertIn("overall_status", payload)
        # v1.2 slim: 3 active adapters (opencode + trae + generic)
        self.assertEqual(len(payload["sources"]), 3)

    def test_panel_mode_does_not_crash_under_cp1252(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "sources"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"CLI crashed under cp1252\nstderr={result.stderr.decode('latin-1', errors='replace')}",
        )
        self.assertNotIn(b"UnicodeEncodeError", result.stderr)

    def test_locate_opencode_runs_and_surfaces_storage(self) -> None:
        """locate-opencode must never crash and must print the table header
        plus next-step instructions (env var hint or binary search hint)."""
        result = self._run_cli(["locate-opencode"], check=False)
        self.assertIn(result.returncode, (0, 1))  # 0 if found, 1 if nothing
        self.assertIn("Locate OpenCode", result.stdout)
        self.assertIn("scanned", result.stdout)
        combined = result.stdout + result.stderr
        # Either a table with columns OR an explicit "not found" message.
        has_table = "sessions" in combined and "msgs" in combined and "today" in combined
        has_not_found = "No OpenCode storage found" in combined
        self.assertTrue(has_table or has_not_found, f"unexpected output: {combined[:500]}")

    def test_default_opencode_roots_include_cli_suffix_variant(self) -> None:
        """Regression: Windows `opencode-cli.exe` installs often write to
        `%APPDATA%\\opencode-cli\\` which was missing from the default root
        list — causing desktop-works-CLI-returns-0 mismatches."""
        from core.config import default_opencode_roots
        roots = default_opencode_roots(
            os_name="nt",
            home=Path("C:/Users/Test"),
            appdata="C:/Users/Test/AppData/Roaming",
            localappdata="C:/Users/Test/AppData/Local",
        )
        root_strs = {str(r).replace("\\", "/") for r in roots}
        # Must cover both the desktop and CLI naming variants
        self.assertTrue(any("opencode-cli" in s for s in root_strs),
                        f"opencode-cli variant missing from Windows defaults: {root_strs}")
        self.assertTrue(any(s.endswith("/OpenCode") for s in root_strs))
        self.assertTrue(any(s.endswith("/opencode") for s in root_strs))

    def test_bootstrap_prompt_shows_absolute_cli_path(self) -> None:
        result = self._run_cli(["bootstrap-prompt"])

        self.assertIn("token-usage-universal", result.stdout)
        self.assertIn(str(CLI_PATH), result.stdout)
        self.assertIn("触发词", result.stdout)
        self.assertIn("ascii-hifi", result.stdout)
        self.assertIn("chcp 65001", result.stdout)
        self.assertIn("PYTHONIOENCODING", result.stdout)

    def test_pythonioencoding_gbk_produces_gbk_decodable_bytes(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "gbk:backslashreplace"
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "sources"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        decoded = result.stdout.decode("gbk", errors="strict")
        self.assertIn("Token Usage", decoded)
        self.assertIn("来源", decoded)

    def test_ingress_config_json_exposes_local_base_url(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "config",
                "--provider",
                "deepseek",
                "--upstream-base-url",
                "https://api.deepseek.com",
                "--protocol",
                "openai",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["provider"], "deepseek")
        self.assertEqual(payload["local_base_url"], "http://127.0.0.1:8787/v1")
        self.assertEqual(payload["upstream_base_url"], "https://api.deepseek.com/v1")

    def test_ingress_profiles_json_lists_bootstrap_catalog(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "profiles",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        profile_ids = {item["profile_id"] for item in payload["profiles"]}
        self.assertIn("openai", profile_ids)
        self.assertIn("anthropic", profile_ids)
        self.assertIn("gemini", profile_ids)
        self.assertIn("openrouter", profile_ids)
        self.assertIn("perplexity", profile_ids)
        self.assertIn("xai", profile_ids)
        self.assertIn("mistral", profile_ids)
        self.assertIn("stepfun", profile_ids)
        self.assertIn("qwen", profile_ids)
        self.assertIn("kimi", profile_ids)
        self.assertIn("glm", profile_ids)
        self.assertIn("doubao", profile_ids)
        self.assertIn("minimax", profile_ids)
        self.assertIn("deepseek", profile_ids)
        self.assertIn("anthropic-compatible", profile_ids)
        self.assertIn("spark", profile_ids)
        self.assertEqual(payload["summary"]["profiles"], 22)

    def test_ingress_bootstrap_json_outputs_continue_snippet(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "bootstrap",
                "--profile",
                "qianfan",
                "--editor",
                "jetbrains",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"]["profile_id"], "qianfan")
        self.assertEqual(payload["editor"]["id"], "jetbrains")
        self.assertIn("provider: openai", payload["continue"]["snippet"])
        self.assertIn("ernie-4.5-turbo-32k", payload["continue"]["snippet"])
        self.assertIn("OPENAI_BASE_URL", payload["cli"]["shell_exports"])

    def test_ingress_bootstrap_json_outputs_official_anthropic_profile(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "bootstrap",
                "--profile",
                "anthropic",
                "--editor",
                "vscode",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"]["profile_id"], "anthropic")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.anthropic.com")
        self.assertIn("provider: anthropic", payload["continue"]["snippet"])
        self.assertIn("claude-sonnet-4-20250514", payload["continue"]["snippet"])

    def test_ingress_bootstrap_json_outputs_qwen_profile(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "bootstrap",
                "--profile",
                "qwen",
                "--editor",
                "vscode",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"]["profile_id"], "qwen")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/compatible-mode/v1")
        self.assertIn("qwen3-coder-plus", payload["continue"]["snippet"])

    def test_ingress_bootstrap_json_outputs_glm_profile(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "bootstrap",
                "--profile",
                "glm",
                "--editor",
                "jetbrains",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"]["profile_id"], "glm")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/api/coding/paas/v4")
        self.assertIn("glm-4.7", payload["continue"]["snippet"])

    def test_ingress_bootstrap_json_outputs_perplexity_root_base_profile(self) -> None:
        result = self._run_cli(
            [
                "ingress",
                "bootstrap",
                "--profile",
                "perplexity",
                "--editor",
                "vscode",
                "--format",
                "json",
            ],
            env=os.environ.copy(),
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"]["profile_id"], "perplexity")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.perplexity.ai")
        self.assertIn("sonar-pro", payload["continue"]["snippet"])


if __name__ == "__main__":
    unittest.main()
