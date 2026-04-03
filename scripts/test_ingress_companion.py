from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.ingress_companion import (
    build_ingress_companion_config,
    build_ingress_companion_payload,
    create_ingress_companion_server,
)


class _UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length)
        request_payload = json.loads(raw_body.decode("utf-8"))
        response_payload = {
            "id": "resp-1",
            "model": request_payload.get("model", "deepseek-chat"),
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            },
        }
        body = json.dumps(response_payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # pragma: no cover
        return


class IngressCompanionTests(unittest.TestCase):
    def test_openai_bootstrap_normalizes_local_v1_base_url(self) -> None:
        config = build_ingress_companion_config(
            provider="deepseek",
            upstream_base_url="https://api.deepseek.com",
            protocol="openai",
            listen_port=8787,
        )
        payload = build_ingress_companion_payload(config)

        self.assertEqual(payload["local_base_url"], "http://127.0.0.1:8787/v1")
        self.assertEqual(payload["upstream_base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(payload["env_hints"]["OPENAI_BASE_URL"], "http://127.0.0.1:8787/v1")

    def test_anthropic_bootstrap_preserves_root_base_url(self) -> None:
        config = build_ingress_companion_config(
            provider="anthropic",
            upstream_base_url="https://api.anthropic.com",
            protocol="anthropic",
            listen_port=8788,
        )
        payload = build_ingress_companion_payload(config)

        self.assertEqual(payload["local_base_url"], "http://127.0.0.1:8788")
        self.assertEqual(payload["env_hints"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8788")

    def test_proxy_logs_exact_usage_jsonl_for_openai_compatible_response(self) -> None:
        upstream = HTTPServer(("127.0.0.1", 0), _UpstreamHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()

        with tempfile.TemporaryDirectory() as tmp:
            config = build_ingress_companion_config(
                provider="deepseek",
                upstream_base_url=f"http://127.0.0.1:{upstream.server_address[1]}",
                protocol="openai",
                listen_port=0,
                log_root=tmp,
                project_path="/tmp/demo-project",
            )
            server = create_ingress_companion_server(config)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions",
                    data=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer demo"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                upstream.shutdown()
                upstream.server_close()

            self.assertEqual(payload["usage"]["total_tokens"], 150)
            logs = sorted((Path(tmp) / "logs").rglob("*.jsonl"))
            self.assertEqual(len(logs), 1)
            records = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines() if line.strip()]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["provider"], "deepseek")
        self.assertEqual(records[0]["project_path"], "/tmp/demo-project")
        self.assertEqual(records[0]["model"], "deepseek-chat")
        self.assertEqual(records[0]["usage"]["total_tokens"], 150)
        self.assertEqual(records[0]["request_url"], f"http://127.0.0.1:{upstream.server_address[1]}/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
