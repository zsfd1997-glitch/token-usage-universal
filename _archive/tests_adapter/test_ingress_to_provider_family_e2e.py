from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.compatible_api_family import build_provider_api_adapters
from core.aggregator import build_report
from core.config import TOKEN_USAGE_DISCOVERY_ROOTS_ENV, TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
from core.ingress_companion import build_ingress_companion_config, create_ingress_companion_server
from core.models import TimeWindow
from test_time import PACIFIC_TZ


class _UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        request_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        response_payload = {
            "id": "resp-e2e-1",
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


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 1, 1, 0, 0, tzinfo=PACIFIC_TZ),
        end=datetime(2026, 12, 31, 23, 59, tzinfo=PACIFIC_TZ),
        label="2026 full-year ingress e2e window",
        timezone_name="US/Pacific",
    )


class IngressToProviderFamilyE2ETests(unittest.TestCase):
    def test_ingress_logged_jsonl_is_auto_discovered_by_provider_adapter(self) -> None:
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
                project_path="/tmp/e2e-provider-family",
            )
            server = create_ingress_companion_server(config)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions",
                    data=json.dumps(
                        {
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": "hello"}],
                        }
                    ).encode("utf-8"),
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

            adapter_map = {adapter.source_id: adapter for adapter in build_provider_api_adapters()}
            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_DISCOVERY_ROOTS_ENV: tmp,
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: "",
                },
                clear=False,
            ):
                result = adapter_map["deepseek-api"].collect(_window())
                report = build_report([result], window=_window(), group_by=None, limit=5)

        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].source, "deepseek-api")
        self.assertEqual(result.events[0].provider, "deepseek")
        self.assertEqual(result.events[0].session_id, "resp-e2e-1")
        self.assertEqual(result.events[0].project_path, "/tmp/e2e-provider-family")
        self.assertEqual(result.events[0].total_tokens, 150)
        self.assertEqual(report["summary"]["total_tokens"], 150)
        self.assertEqual(report["summary"]["effective_tokens"], 150)
        self.assertEqual(report["by_source"][0]["name"], "deepseek-api")


if __name__ == "__main__":
    unittest.main()
