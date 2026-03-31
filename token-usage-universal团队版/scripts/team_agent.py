#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request

from team_common import build_ingest_event, build_local_window, build_time_window, load_local_collectors, parse_last


DEFAULT_STATE_ROOT = Path.home() / ".codex" / "cache" / "token-usage-team-edition"


def _default_state_file(server_url: str, team_id: str, user_id: str, machine_id: str) -> Path:
    digest = hashlib.sha1(f"{server_url}|{team_id}|{user_id}|{machine_id}".encode("utf-8")).hexdigest()[:12]
    return DEFAULT_STATE_ROOT / f"{digest}.json"


def _read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _post_events(server_url: str, agent_token: str, events: list[dict[str, object]], timeout: float) -> dict[str, object]:
    body = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{server_url.rstrip('/')}/api/ingest",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Agent-Token": agent_token,
        },
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _collect_events(args, *, start: str | None, end: str | None) -> tuple[list[dict[str, object]], dict[str, int]]:
    registry = load_local_collectors()
    selected_sources = args.source or list(registry.keys())
    machine_id = args.machine_id or socket.gethostname()
    machine_label = args.machine_label or machine_id
    exported_at = datetime.now().astimezone().isoformat()
    window = build_local_window(today=False, last=None, start=start, end=end, tz_name=args.tz)

    events: list[dict[str, object]] = []
    source_counts: dict[str, int] = {}
    for source_id in selected_sources:
        adapter_cls = registry.get(source_id)
        if adapter_cls is None:
            raise SystemExit(f"unknown source: {source_id}")
        result = adapter_cls().collect(window)
        source_counts[source_id] = len(result.events)
        for event in result.events:
            events.append(
                build_ingest_event(
                    event,
                    team_id=args.team_id,
                    user_id=args.user_id,
                    machine_id=machine_id,
                    machine_label=machine_label,
                    exported_at=exported_at,
                )
            )
    return events, source_counts


def _resolve_window_from_state(args, state: dict[str, object]) -> tuple[str, str]:
    now = datetime.now().astimezone()
    if args.start or args.end:
        start = args.start or state.get("last_success_end")
        end = args.end or now.isoformat()
        if not start:
            raise SystemExit("explicit start/end mode requires --start when state is empty")
        return str(start), str(end)

    if state.get("last_success_end"):
        return str(state["last_success_end"]), now.isoformat()

    bootstrap_last = args.bootstrap_last or "24h"
    bootstrap_window = build_time_window(
        today=False,
        last=bootstrap_last,
        start=None,
        end=None,
        tz_name=args.tz,
        default_mode=f"last:{bootstrap_last}",
    )
    return str(bootstrap_window.start.isoformat()), str(bootstrap_window.end.isoformat())


def run_once(args) -> dict[str, object]:
    machine_id = args.machine_id or socket.gethostname()
    state_file = args.state_file or _default_state_file(args.server_url, args.team_id, args.user_id, machine_id)
    state = _read_state(state_file)
    start, end = _resolve_window_from_state(args, state)
    events, source_counts = _collect_events(args, start=start, end=end)

    if args.dry_run:
        return {
            "mode": "dry-run",
            "state_file": str(state_file),
            "start": start,
            "end": end,
            "events_collected": len(events),
            "source_counts": source_counts,
        }

    response = _post_events(args.server_url, args.agent_token, events, args.timeout)
    state_payload = {
        "last_success_end": end,
        "last_attempted_start": start,
        "last_run_at": datetime.now().astimezone().isoformat(),
        "last_response": response,
    }
    _write_state(state_file, state_payload)
    return {
        "state_file": str(state_file),
        "start": start,
        "end": end,
        "events_collected": len(events),
        "source_counts": source_counts,
        "server_response": response,
    }


def command_once(args) -> int:
    payload = run_once(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_run(args) -> int:
    while True:
        try:
            payload = run_once(args)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        except error.URLError as exc:
            print(json.dumps({"error": str(exc), "server_url": args.server_url}, ensure_ascii=False, indent=2))
        except Exception as exc:  # pragma: no cover
            print(json.dumps({"error": repr(exc)}, ensure_ascii=False, indent=2))
        time.sleep(args.interval)


def command_state(args) -> int:
    machine_id = args.machine_id or socket.gethostname()
    state_file = args.state_file or _default_state_file(args.server_url, args.team_id, args.user_id, machine_id)
    payload = {
        "state_file": str(state_file),
        "exists": state_file.exists(),
        "state": _read_state(state_file),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Token Usage Universal Team Agent")
    parser.add_argument("--server-url", required=True, help="central backend URL, e.g. http://10.0.0.8:8787")
    parser.add_argument("--agent-token", required=True, help="device-specific ingest token from issue-agent-token")
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--machine-id", help="stable machine identifier; defaults to hostname")
    parser.add_argument("--machine-label", help="human-readable machine label")
    parser.add_argument("--state-file", type=Path, help="override incremental state file path")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--tz", default="Asia/Shanghai")
    parser.add_argument("--source", action="append", help="limit to specific source ids")

    subparsers = parser.add_subparsers(dest="command", required=True)

    once = subparsers.add_parser("once", help="collect and push one incremental batch")
    once.add_argument("--start", help="manual window start in ISO format")
    once.add_argument("--end", help="manual window end in ISO format")
    once.add_argument("--bootstrap-last", default="24h", help="initial backfill window when state is empty")
    once.add_argument("--dry-run", action="store_true")
    once.set_defaults(func=command_once)

    run = subparsers.add_parser("run", help="run forever and push on interval")
    run.add_argument("--bootstrap-last", default="24h", help="initial backfill window when state is empty")
    run.add_argument("--interval", type=int, default=300, help="seconds between sync cycles")
    run.set_defaults(func=command_run)

    state = subparsers.add_parser("state", help="inspect local agent checkpoint")
    state.set_defaults(func=command_state)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
