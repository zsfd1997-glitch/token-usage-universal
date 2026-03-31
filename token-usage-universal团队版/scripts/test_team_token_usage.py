from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "team_token_usage.py"
SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "team-usage.sample.jsonl"


class TeamTokenUsageTests(unittest.TestCase):
    def test_health_and_report_on_sample_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            team_dir = Path(root) / "demo-team" / "raw" / "alice" / "alice-mbp"
            team_dir.mkdir(parents=True)
            target = team_dir / "sample.jsonl"
            target.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

            env = os.environ.copy()
            env["TOKEN_USAGE_TEAM_LOG_ROOT"] = root

            health = subprocess.run(
                ["python3", str(SCRIPT), "health", "--team-id", "demo-team", "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            health_payload = json.loads(health.stdout)
            self.assertTrue(health_payload["exists"])
            self.assertEqual(health_payload["files"], 1)

            report = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "report",
                    "--team-id",
                    "demo-team",
                    "--start",
                    "2026-03-30T00:00:00-07:00",
                    "--end",
                    "2026-03-30T23:59:59-07:00",
                    "--by",
                    "user",
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(report.stdout)
            self.assertEqual(payload["summary"]["users"], 3)
            self.assertEqual(payload["summary"]["events"], 4)
            self.assertEqual(payload["grouped"][0]["name"], "alice")
            self.assertEqual(payload["grouped"][0]["tokens"], 4480)


if __name__ == "__main__":
    unittest.main()
