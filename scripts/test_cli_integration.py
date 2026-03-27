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
    def test_report_json_works_with_generic_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "generic.jsonl"
            log_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-25T09:00:00-07:00",
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
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(log_file)
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "report",
                    "--start",
                    "2026-03-25T00:00:00-07:00",
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
            self.assertEqual(payload["report"]["summary"]["total_tokens"], 1100)
            self.assertEqual(payload["report"]["by_model"][0]["name"], "qwen-max")

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
        self.assertEqual(source_ids, ["codex", "claude-code", "generic-openai-compatible"])
        self.assertIn("overall_status", payload)


if __name__ == "__main__":
    unittest.main()
