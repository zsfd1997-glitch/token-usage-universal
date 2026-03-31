from __future__ import annotations

import http.cookiejar
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import parse, request

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from team_backend import create_admin_user, create_server, init_database, issue_agent_token


class TeamBackendIntegrationTests(unittest.TestCase):
    def test_ingest_login_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "team.db"
            init_database(db_path)
            create_admin_user(db_path, "admin", "pass-123")
            token_payload = issue_agent_token(
                db_path,
                team_id="demo-team",
                user_id="alice",
                machine_id="alice-mbp",
                machine_label="Alice MacBook Pro",
                note="integration",
            )

            server = create_server(db_path, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base_url = f"http://{host}:{port}"

            try:
                timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
                payload = {
                    "events": [
                        {
                            "event_id": "evt-1",
                            "source": "codex",
                            "provider": "openai",
                            "model": "gpt-5.4",
                            "session_id": "sess-1",
                            "project_path": "/srv/demo",
                            "timestamp": timestamp,
                            "input_tokens": 1200,
                            "cached_input_tokens": 200,
                            "output_tokens": 300,
                            "reasoning_tokens": 40,
                            "total_tokens": 1500,
                            "accuracy_level": "exact",
                            "raw_event_kind": "token_count:delta",
                            "source_path": "/tmp/source.jsonl",
                            "machine_label": "Alice MacBook Pro",
                        }
                    ]
                }
                req = request.Request(
                    f"{base_url}/api/ingest",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "X-Agent-Token": token_payload["token"],
                    },
                    method="POST",
                )
                with request.urlopen(req, timeout=5) as resp:
                    ingest_result = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(ingest_result["inserted"], 1)

                jar = http.cookiejar.CookieJar()
                opener = request.build_opener(request.HTTPCookieProcessor(jar))
                login_body = parse.urlencode({"username": "admin", "password": "pass-123"}).encode("utf-8")
                login_req = request.Request(f"{base_url}/login", data=login_body, method="POST")
                with opener.open(login_req, timeout=5) as resp:
                    self.assertEqual(resp.geturl(), f"{base_url}/dashboard")

                with opener.open(f"{base_url}/api/me", timeout=5) as resp:
                    me_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(me_payload["username"], "admin")
                self.assertEqual(me_payload["teams"], ["demo-team"])

                with opener.open(f"{base_url}/api/dashboard?team_id=demo-team&range=7d&limit=5", timeout=5) as resp:
                    dashboard_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(dashboard_payload["summary"]["events"], 1)
                self.assertEqual(dashboard_payload["summary"]["users"], 1)
                self.assertEqual(dashboard_payload["by_user"][0]["name"], "alice")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
