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
    def _run_cli(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
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
        self.assertEqual(len(source_ids), 51)
        self.assertIn("codex", source_ids)
        self.assertIn("claude-code", source_ids)
        self.assertIn("claude-desktop", source_ids)
        self.assertIn("opencode", source_ids)
        self.assertIn("trae", source_ids)
        self.assertIn("minimax-agent", source_ids)
        self.assertIn("qwen-code-cli", source_ids)
        self.assertIn("kimi-cli", source_ids)
        self.assertIn("gemini-cli", source_ids)
        self.assertIn("kimi-desktop", source_ids)
        self.assertIn("glm-desktop", source_ids)
        self.assertIn("stepfun-desktop", source_ids)
        self.assertIn("chatgpt-desktop", source_ids)
        self.assertIn("gemini-desktop", source_ids)
        self.assertIn("qwen-desktop", source_ids)
        self.assertIn("deepseek-desktop", source_ids)
        self.assertIn("doubao-desktop", source_ids)
        self.assertIn("qianfan-desktop", source_ids)
        self.assertIn("yuanbao-desktop", source_ids)
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
        result = self._run_cli(["explore"], check=False, env=os.environ.copy())

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("interactive TTY", result.stderr or result.stdout)

    def test_targets_json_exposes_frozen_registry(self) -> None:
        result = self._run_cli(["targets", "--format", "json"], env=os.environ.copy())

        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total_ecosystems"], 20)
        self.assertEqual(payload["summary"]["china_priority_ecosystems"], 13)
        self.assertEqual(payload["summary"]["surface_maturity"]["exact-ready"], 60)
        self.assertEqual(payload["summary"]["surface_maturity"].get("detect-ready", 0), 0)
        self.assertEqual(payload["scope"]["surfaces"], ["desktop", "cli", "ide"])

    def test_targets_json_survives_legacy_stdout_encoding(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"
        result = self._run_cli(["targets", "--format", "json"], env=env)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total_ecosystems"], 20)

    def test_health_json_survives_legacy_stdout_encoding(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252"
        result = self._run_cli(["health", "--format", "json"], env=env)

        payload = json.loads(result.stdout)
        self.assertIn("overall_status", payload)
        self.assertEqual(len(payload["sources"]), 51)

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

    def test_release_gate_json_exposes_automated_gate_status(self) -> None:
        result = self._run_cli(["release-gate", "--format", "json"], env=os.environ.copy())

        payload = json.loads(result.stdout)
        gate_ids = {item["gate_id"] for item in payload["gates"]}
        self.assertEqual(payload["summary"]["status"], "pass")
        self.assertIn("top20-coverage", gate_ids)
        self.assertIn("false-ready-claims", gate_ids)
        self.assertIn("default-report-duplicate-rate", gate_ids)
        self.assertIn("windows-macos-linux-root-matrix", gate_ids)
        self.assertEqual(payload["registry_summary"]["surface_maturity"]["exact-ready"], 60)
        self.assertEqual(payload["metrics"]["default_duplicate_event_ratio"], 0.0)
        self.assertEqual(payload["metrics"]["linux_root_coverage_ratio"], 1.0)

    def test_release_gate_can_write_release_evidence_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "release-evidence"
            result = self._run_cli(
                [
                    "release-gate",
                    "--format",
                    "json",
                    "--output-dir",
                    str(output_dir),
                ],
                env=os.environ.copy(),
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["status"], "pass")
            self.assertTrue((output_dir / "release_gate.json").exists())
            self.assertTrue((output_dir / "health.json").exists())
            self.assertTrue((output_dir / "sources.json").exists())
            self.assertTrue((output_dir / "targets.json").exists())
            self.assertTrue((output_dir / "report_today.json").exists())
            self.assertTrue((output_dir / "report_recent_30d.json").exists())
            self.assertTrue((output_dir / "SUMMARY.md").exists())
            self.assertTrue((output_dir / "diagnose").is_dir())
            summary_text = (output_dir / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Release Evidence Bundle", summary_text)
            release_payload = json.loads((output_dir / "release_gate.json").read_text(encoding="utf-8"))
            self.assertEqual(release_payload["summary"]["status"], "pass")

    def test_release_gate_can_diff_against_baseline_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline_dir = tmp_path / "baseline"
            baseline_dir.mkdir(parents=True)
            output_dir = tmp_path / "release-evidence"
            (baseline_dir / "sources.json").write_text(
                json.dumps(
                    [
                        {
                            "source_id": "synthetic-source",
                            "state": "exact",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self._run_cli(
                [
                    "release-gate",
                    "--format",
                    "json",
                    "--baseline",
                    str(baseline_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                env=os.environ.copy(),
            )

            payload = json.loads(result.stdout)
            self.assertIn("baseline", payload)
            self.assertEqual(payload["baseline"]["diff"]["counts"]["removed_sources"], 1)
            self.assertIn("synthetic-source", payload["baseline"]["diff"]["removed_sources"])
            self.assertTrue((output_dir / "diff.json").exists())

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
