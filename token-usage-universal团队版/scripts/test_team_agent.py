from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from team_backend import build_dashboard_payload, create_server, init_database, issue_agent_token
from team_common import build_time_window


AGENT = Path(__file__).resolve().parent / "team_agent.py"
GENERIC_SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "generic-usage.sample.jsonl"


class TeamAgentTests(unittest.TestCase):
    def test_agent_once_pushes_sample_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "team.db"
            state_path = Path(tmp) / "agent-state.json"
            init_database(db_path)
            token_payload = issue_agent_token(
                db_path,
                team_id="demo-team",
                user_id="qa",
                machine_id="qa-mac",
                machine_label="QA Mac",
                note="agent-test",
            )
            server = create_server(db_path, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base_url = f"http://{host}:{port}"
            try:
                env = os.environ.copy()
                env["TOKEN_USAGE_GENERIC_LOG_GLOBS"] = str(GENERIC_SAMPLE)
                subprocess.run(
                    [
                        "python3",
                        str(AGENT),
                        "--server-url",
                        base_url,
                        "--agent-token",
                        token_payload["token"],
                        "--team-id",
                        "demo-team",
                        "--user-id",
                        "qa",
                        "--machine-id",
                        "qa-mac",
                        "--state-file",
                        str(state_path),
                        "--source",
                        "generic-openai-compatible",
                        "once",
                        "--start",
                        "2026-03-25T00:00:00-07:00",
                        "--end",
                        "2026-03-25T23:59:59-07:00",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )

                payload = build_dashboard_payload(
                    db_path,
                    team_id="demo-team",
                    window=build_time_window(
                        today=False,
                        last=None,
                        start="2026-03-25T00:00:00-07:00",
                        end="2026-03-25T23:59:59-07:00",
                        tz_name="Asia/Shanghai",
                        default_mode="all",
                    ),
                    limit=5,
                )
                self.assertEqual(payload["summary"]["events"], 2)
                self.assertEqual(payload["summary"]["effective_tokens"], 2330)
                self.assertEqual(payload["by_source"][0]["name"], "generic-openai-compatible")
                self.assertTrue(state_path.exists())
                state_payload = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertIn("last_success_end", state_payload)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
