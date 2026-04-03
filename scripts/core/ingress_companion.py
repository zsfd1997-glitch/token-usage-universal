from __future__ import annotations

import json
import os
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

from core.config import expand_path_text
from core.usage_records import MODEL_KEYS, SESSION_KEYS, find_first_value, find_usage_dict, normalize_usage


def _default_ingress_log_root(provider: str) -> Path:
    home = Path.home()
    safe_provider = provider.strip().lower().replace("/", "-").replace("_", "-") or "generic"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", "") or (home / "AppData" / "Local"))
        return base / f"{safe_provider}-ingress"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / f"{safe_provider}-ingress"
    return home / ".local" / "share" / f"{safe_provider}-ingress"


def _normalize_protocol(protocol: str) -> str:
    value = protocol.strip().lower()
    if value not in {"openai", "anthropic", "generic"}:
        raise ValueError(f"unsupported ingress protocol: {protocol}")
    return value


def _normalize_base_path(path: str) -> str:
    if not path:
        return ""
    normalized = "/" + path.strip().strip("/")
    return "" if normalized == "/" else normalized


def _normalize_upstream_base_url(upstream_base_url: str, protocol: str, explicit_local_base_path: str | None = None) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(upstream_base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("upstream_base_url must include http(s) scheme and host")

    upstream_path = parsed.path.rstrip("/")
    if explicit_local_base_path is not None:
        local_base_path = _normalize_base_path(explicit_local_base_path)
        if local_base_path and not upstream_path.endswith(local_base_path):
            upstream_path = (upstream_path + local_base_path).rstrip("/")
    elif protocol == "openai":
        local_base_path = "/v1"
        if upstream_path in {"", "/"}:
            upstream_path = "/v1"
        elif upstream_path.endswith("/v1"):
            local_base_path = "/v1"
        else:
            local_base_path = _normalize_base_path(upstream_path)
    else:
        local_base_path = _normalize_base_path(upstream_path)

    normalized = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, upstream_path or "", parsed.query, parsed.fragment)
    )
    return normalized.rstrip("/"), local_base_path


@dataclass(frozen=True)
class IngressCompanionConfig:
    provider: str
    upstream_base_url: str
    protocol: str
    listen_host: str
    listen_port: int
    local_base_path: str
    log_root: Path
    project_path: str | None = None


def build_ingress_companion_config(
    *,
    provider: str,
    upstream_base_url: str,
    protocol: str,
    listen_host: str = "127.0.0.1",
    listen_port: int = 8787,
    local_base_path: str | None = None,
    log_root: str | Path | None = None,
    project_path: str | None = None,
) -> IngressCompanionConfig:
    normalized_protocol = _normalize_protocol(protocol)
    normalized_upstream, normalized_base_path = _normalize_upstream_base_url(
        upstream_base_url,
        normalized_protocol,
        explicit_local_base_path=local_base_path,
    )
    resolved_log_root = Path(expand_path_text(str(log_root))).expanduser() if log_root else _default_ingress_log_root(provider)
    return IngressCompanionConfig(
        provider=provider.strip().lower(),
        upstream_base_url=normalized_upstream,
        protocol=normalized_protocol,
        listen_host=listen_host,
        listen_port=int(listen_port),
        local_base_path=normalized_base_path,
        log_root=resolved_log_root,
        project_path=project_path,
    )


def build_ingress_companion_payload(config: IngressCompanionConfig) -> dict[str, object]:
    local_base_url = f"http://{config.listen_host}:{config.listen_port}{config.local_base_path}"
    env_hints: dict[str, str] = {}
    if config.protocol == "openai":
        env_hints["OPENAI_BASE_URL"] = local_base_url
    elif config.protocol == "anthropic":
        env_hints["ANTHROPIC_BASE_URL"] = local_base_url

    return {
        "provider": config.provider,
        "protocol": config.protocol,
        "upstream_base_url": config.upstream_base_url,
        "listen_host": config.listen_host,
        "listen_port": config.listen_port,
        "local_base_path": config.local_base_path,
        "local_base_url": local_base_url,
        "log_root": str(config.log_root),
        "project_path": config.project_path,
        "env_hints": env_hints,
        "notes": [
            "Keep your original API key; only swap the client base_url to the local companion.",
            "Exact usage logs are written as JSONL and are auto-discovered by provider-family adapters.",
        ],
    }


def render_ingress_companion_payload(payload: dict[str, object]) -> str:
    lines = [
        "Ingress Companion",
        f"Provider: {payload['provider']}",
        f"Protocol: {payload['protocol']}",
        f"Local Base URL: {payload['local_base_url']}",
        f"Upstream Base URL: {payload['upstream_base_url']}",
        f"Log Root: {payload['log_root']}",
    ]
    if payload.get("project_path"):
        lines.append(f"Project Path: {payload['project_path']}")
    env_hints = payload.get("env_hints", {})
    if env_hints:
        lines.append("Client Config:")
        for key, value in env_hints.items():
            lines.append(f"  {key}={value}")
    lines.append("Start Command:")
    lines.append(
        "  python3 scripts/token_usage.py ingress serve "
        f"--provider {payload['provider']} --protocol {payload['protocol']} "
        f"--upstream-base-url {payload['upstream_base_url']} --listen-host 127.0.0.1 --listen-port {payload['listen_port']}"
    )
    return "\n".join(lines)


def _load_json_payload(raw_body: bytes, content_type: str) -> object | None:
    if "json" not in content_type.lower():
        return None
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _extract_sse_payloads(raw_body: bytes) -> list[object]:
    payloads: list[object] = []
    text = raw_body.decode("utf-8", errors="ignore")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        value = line[5:].strip()
        if not value or value == "[DONE]":
            continue
        try:
            payloads.append(json.loads(value))
        except json.JSONDecodeError:
            continue
    return payloads


def _normalize_usage_payload(payload: object) -> dict[str, int] | None:
    usage = find_usage_dict(payload)
    if not usage:
        return None
    normalized = normalize_usage(usage)
    if normalized["total_tokens"] <= 0:
        return None
    return normalized


def _extract_capture_record(
    *,
    provider: str,
    protocol: str,
    target_url: str,
    base_url: str,
    request_payload: object | None,
    response_payload: object | None,
    sse_payloads: list[object],
    response_status: int,
    project_path: str | None,
) -> dict[str, object] | None:
    usage_payload = _normalize_usage_payload(response_payload)
    usage_owner: object | None = response_payload
    if usage_payload is None:
        for item in reversed(sse_payloads):
            usage_payload = _normalize_usage_payload(item)
            if usage_payload is not None:
                usage_owner = item
                break
    if usage_payload is None:
        return None

    merged_sources = [response_payload, *reversed(sse_payloads), request_payload]
    model = None
    session_id = None
    for payload in merged_sources:
        if payload is None:
            continue
        if model is None:
            model = find_first_value(payload, MODEL_KEYS)
        if session_id is None:
            session_id = find_first_value(payload, SESSION_KEYS)
        if model is not None and session_id is not None:
            break

    request_summary = {}
    if isinstance(request_payload, dict):
        for key in ("model", "stream", "max_tokens", "temperature"):
            if key in request_payload:
                request_summary[key] = request_payload[key]

    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "provider": provider,
        "protocol": protocol,
        "request_url": target_url,
        "base_url": base_url,
        "session_id": str(session_id or uuid4()),
        "project_path": project_path,
        "model": model,
        "usage": usage_payload,
        "response_status": response_status,
        "request": request_summary,
        "response_model_source": "response" if usage_owner is response_payload else "stream",
    }


def _write_capture_record(record: dict[str, object], log_root: Path) -> Path:
    timestamp = datetime.fromisoformat(str(record["timestamp"]))
    log_dir = log_root / "logs" / timestamp.strftime("%Y-%m")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{timestamp.strftime('%Y-%m-%d')}.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log_path


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


class _IngressProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self) -> None:  # pragma: no cover
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        self._handle_proxy()

    def do_POST(self) -> None:
        self._handle_proxy()

    def do_PUT(self) -> None:  # pragma: no cover
        self._handle_proxy()

    def do_PATCH(self) -> None:  # pragma: no cover
        self._handle_proxy()

    def do_DELETE(self) -> None:  # pragma: no cover
        self._handle_proxy()

    def log_message(self, format: str, *args) -> None:  # pragma: no cover
        return

    @property
    def config(self) -> IngressCompanionConfig:
        return self.server.config  # type: ignore[attr-defined]

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")

    def _proxy_target_url(self) -> str:
        incoming = urllib.parse.urlsplit(self.path)
        request_path = incoming.path or "/"
        base_path = self.config.local_base_path
        if base_path and request_path.startswith(base_path):
            request_path = request_path[len(base_path) :] or "/"

        upstream = urllib.parse.urlsplit(self.config.upstream_base_url)
        joined_path = upstream.path.rstrip("/")
        if request_path:
            joined_path = f"{joined_path}/{request_path.lstrip('/')}" if joined_path else request_path
        return urllib.parse.urlunsplit((upstream.scheme, upstream.netloc, joined_path or "/", incoming.query, ""))

    def _forward_headers(self) -> dict[str, str]:
        excluded = {"host", "content-length", "accept-encoding", "connection"}
        return {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in excluded
        }

    def _handle_proxy(self) -> None:
        body = b""
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length > 0:
            body = self.rfile.read(content_length)

        target_url = self._proxy_target_url()
        request_payload = _load_json_payload(body, self.headers.get("Content-Type", ""))
        request = urllib.request.Request(
            target_url,
            data=body if self.command not in {"GET", "DELETE"} else None,
            headers=self._forward_headers(),
            method=self.command,
        )

        response_status = 502
        response_headers: list[tuple[str, str]] = []
        response_body = b""
        content_type = ""
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response_status = response.status
                response_headers = list(response.getheaders())
                content_type = response.headers.get("Content-Type", "")
                if "text/event-stream" in content_type.lower():
                    self.send_response(response_status)
                    for key, value in response_headers:
                        if key.lower() in {"content-length", "transfer-encoding", "connection"}:
                            continue
                        self.send_header(key, value)
                    self._send_cors_headers()
                    self.end_headers()
                    buffer = bytearray()
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        buffer.extend(chunk)
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    response_body = bytes(buffer)
                else:
                    response_body = response.read()
        except urllib.error.HTTPError as exc:
            response_status = exc.code
            response_headers = list(exc.headers.items())
            content_type = exc.headers.get("Content-Type", "")
            response_body = exc.read()
        except urllib.error.URLError as exc:
            payload = json.dumps({"error": f"upstream request failed: {exc.reason}"}, ensure_ascii=False).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if "text/event-stream" not in content_type.lower():
            self.send_response(response_status)
            for key, value in response_headers:
                if key.lower() in {"content-length", "transfer-encoding", "connection"}:
                    continue
                self.send_header(key, value)
            self._send_cors_headers()
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if response_body:
                self.wfile.write(response_body)

        response_payload = _load_json_payload(response_body, content_type)
        sse_payloads = _extract_sse_payloads(response_body) if "text/event-stream" in content_type.lower() else []
        record = _extract_capture_record(
            provider=self.config.provider,
            protocol=self.config.protocol,
            target_url=target_url,
            base_url=self.config.upstream_base_url,
            request_payload=request_payload,
            response_payload=response_payload,
            sse_payloads=sse_payloads,
            response_status=response_status,
            project_path=self.config.project_path,
        )
        if record is not None:
            _write_capture_record(record, self.config.log_root)


def create_ingress_companion_server(config: IngressCompanionConfig) -> _ThreadingHTTPServer:
    server = _ThreadingHTTPServer((config.listen_host, config.listen_port), _IngressProxyHandler)
    server.config = config  # type: ignore[attr-defined]
    return server


def serve_ingress_companion(config: IngressCompanionConfig) -> None:
    server = create_ingress_companion_server(config)
    live_config = IngressCompanionConfig(
        provider=config.provider,
        upstream_base_url=config.upstream_base_url,
        protocol=config.protocol,
        listen_host=config.listen_host,
        listen_port=server.server_address[1],
        local_base_path=config.local_base_path,
        log_root=config.log_root,
        project_path=config.project_path,
    )
    print(render_ingress_companion_payload(build_ingress_companion_payload(live_config)), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()


__all__ = [
    "IngressCompanionConfig",
    "build_ingress_companion_config",
    "build_ingress_companion_payload",
    "create_ingress_companion_server",
    "render_ingress_companion_payload",
    "serve_ingress_companion",
]
