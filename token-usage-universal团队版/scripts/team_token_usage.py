#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


TEAM_LOG_ROOT_ENV = "TOKEN_USAGE_TEAM_LOG_ROOT"


@dataclass(frozen=True)
class TimeWindow:
    start: datetime | None
    end: datetime | None
    label: str
    timezone_name: str


@dataclass(frozen=True)
class TeamUsageEvent:
    event_id: str
    team_id: str
    user_id: str
    machine_id: str
    machine_label: str | None
    source: str
    provider: str
    timestamp: datetime
    session_id: str
    project_path: str | None
    model: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int
    accuracy_level: str
    raw_event_kind: str
    source_path: str
    exported_at: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


def _resolve_tz(name: str | None):
    if name:
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name)
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"invalid timezone: {name}") from exc
    return datetime.now().astimezone().tzinfo


def _coerce_datetime(value: str, tz_name: str | None) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_resolve_tz(tz_name))
    return parsed


def _parse_last(value: str) -> timedelta:
    if value.endswith("d"):
        return timedelta(days=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    raise SystemExit(f"unsupported --last value: {value}")


def build_time_window(*, today: bool, last: str | None, start: str | None, end: str | None, tz_name: str | None) -> TimeWindow:
    tzinfo = _resolve_tz(tz_name)
    now = datetime.now(tzinfo)

    if start or end:
        start_dt = _coerce_datetime(start, tz_name).astimezone(tzinfo) if start else None
        end_dt = _coerce_datetime(end, tz_name).astimezone(tzinfo) if end else now
        return TimeWindow(start=start_dt, end=end_dt, label="custom", timezone_name=str(tzinfo))

    if last:
        duration = _parse_last(last)
        return TimeWindow(start=now - duration, end=now, label=f"last {last}", timezone_name=str(tzinfo))

    if today or not any((today, last, start, end)):
        day_start = datetime(now.year, now.month, now.day, tzinfo=tzinfo)
        return TimeWindow(start=day_start, end=now, label="today", timezone_name=str(tzinfo))

    return TimeWindow(start=None, end=None, label="all", timezone_name=str(tzinfo))


def within_window(window: TimeWindow, timestamp: datetime) -> bool:
    if window.start and timestamp < window.start:
        return False
    if window.end and timestamp > window.end:
        return False
    return True


def _parse_event(payload: dict[str, object]) -> TeamUsageEvent:
    return TeamUsageEvent(
        event_id=str(payload["event_id"]),
        team_id=str(payload["team_id"]),
        user_id=str(payload["user_id"]),
        machine_id=str(payload["machine_id"]),
        machine_label=str(payload.get("machine_label")) if payload.get("machine_label") not in (None, "") else None,
        source=str(payload["source"]),
        provider=str(payload["provider"]),
        timestamp=datetime.fromisoformat(str(payload["timestamp"])),
        session_id=str(payload["session_id"]),
        project_path=payload.get("project_path"),
        model=payload.get("model"),
        input_tokens=int(payload["input_tokens"]) if payload.get("input_tokens") is not None else None,
        cached_input_tokens=int(payload["cached_input_tokens"]) if payload.get("cached_input_tokens") is not None else None,
        output_tokens=int(payload["output_tokens"]) if payload.get("output_tokens") is not None else None,
        reasoning_tokens=int(payload["reasoning_tokens"]) if payload.get("reasoning_tokens") is not None else None,
        total_tokens=int(payload["total_tokens"]),
        accuracy_level=str(payload["accuracy_level"]),
        raw_event_kind=str(payload["raw_event_kind"]),
        source_path=str(payload["source_path"]),
        exported_at=str(payload.get("exported_at")) if payload.get("exported_at") not in (None, "") else None,
    )


def _iter_json_records(path: Path) -> Iterable[dict[str, object]]:
    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if raw_line:
                    yield json.loads(raw_line)
        return

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        for item in payload:
            yield item
    elif isinstance(payload, dict):
        yield payload


def _resolve_team_log_root(args) -> Path:
    root = (args.log_root or os.environ.get(TEAM_LOG_ROOT_ENV, "")).strip()
    if not root:
        raise SystemExit(f"set --log-root or {TEAM_LOG_ROOT_ENV}")
    return Path(root).expanduser()


def _discover_team_files(root: Path, team_id: str | None) -> list[Path]:
    if not root.exists():
        return []
    base = root / team_id if team_id else root
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*") if path.is_file() and path.suffix in {".jsonl", ".json"})


def _effective_tokens(event: TeamUsageEvent) -> int:
    return event.total_tokens - int(event.cached_input_tokens or 0)


def _group_key(event: TeamUsageEvent, by: str, tz_name: str) -> str:
    if by == "user":
        return event.user_id
    if by == "machine":
        return event.machine_id
    if by == "project":
        return event.project_path or "(unknown project)"
    if by == "model":
        return event.model or "(unknown model)"
    if by == "source":
        return event.source
    if by == "day":
        return event.timestamp.astimezone(_resolve_tz(tz_name)).strftime("%Y-%m-%d")
    raise SystemExit(f"unsupported group: {by}")


def _load_team_events(root: Path, *, team_id: str | None, window: TimeWindow, source_filter: list[str], user_filter: list[str]) -> tuple[list[TeamUsageEvent], list[Path]]:
    files = _discover_team_files(root, team_id)
    events: list[TeamUsageEvent] = []
    seen_event_ids: set[str] = set()
    for path in files:
        for record in _iter_json_records(path):
            if "event_id" not in record:
                continue
            event = _parse_event(record)
            if team_id and event.team_id != team_id:
                continue
            if source_filter and event.source not in source_filter:
                continue
            if user_filter and event.user_id not in user_filter:
                continue
            if not within_window(window, event.timestamp):
                continue
            if event.event_id in seen_event_ids:
                continue
            seen_event_ids.add(event.event_id)
            events.append(event)
    events.sort(key=lambda item: item.timestamp)
    return events, files


def _summarize(events: list[TeamUsageEvent]) -> dict[str, object]:
    total_tokens = sum(event.total_tokens for event in events)
    cached_tokens = sum(int(event.cached_input_tokens or 0) for event in events)
    effective_tokens = sum(_effective_tokens(event) for event in events)
    return {
        "events": len(events),
        "users": len({event.user_id for event in events}),
        "machines": len({event.machine_id for event in events}),
        "projects": len({event.project_path or "(unknown project)" for event in events}),
        "sessions": len({event.session_id for event in events}),
        "sources": len({event.source for event in events}),
        "total_tokens": total_tokens,
        "cached_input_tokens": cached_tokens,
        "effective_tokens": effective_tokens,
    }


def _group_rows(events: list[TeamUsageEvent], by: str, limit: int, tz_name: str) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "tokens": 0,
            "effective_tokens": 0,
            "cached_input_tokens": 0,
            "events": 0,
            "users": set(),
            "machines": set(),
            "projects": set(),
            "sources": set(),
            "last_timestamp": None,
        }
    )
    for event in events:
        key = _group_key(event, by, tz_name)
        row = grouped[key]
        row["tokens"] += event.total_tokens
        row["effective_tokens"] += _effective_tokens(event)
        row["cached_input_tokens"] += int(event.cached_input_tokens or 0)
        row["events"] += 1
        row["users"].add(event.user_id)
        row["machines"].add(event.machine_id)
        row["projects"].add(event.project_path or "(unknown project)")
        row["sources"].add(event.source)
        row["last_timestamp"] = max(row["last_timestamp"], event.timestamp) if row["last_timestamp"] else event.timestamp

    rows = []
    for name, row in grouped.items():
        rows.append(
            {
                "name": name,
                "tokens": row["tokens"],
                "effective_tokens": row["effective_tokens"],
                "cached_input_tokens": row["cached_input_tokens"],
                "events": row["events"],
                "users": len(row["users"]),
                "machines": len(row["machines"]),
                "projects": len(row["projects"]),
                "sources": len(row["sources"]),
                "last_timestamp": row["last_timestamp"].isoformat() if row["last_timestamp"] else None,
            }
        )
    rows.sort(key=lambda item: (item["effective_tokens"], item["tokens"], item["events"]), reverse=True)
    return rows[:limit]


def _render_report(payload: dict[str, object]) -> str:
    window = payload["window"]
    summary = payload["summary"]
    lines = [
        "Token Usage Universal Team Edition",
        f"Window: {window['label']}  TZ: {window['timezone']}",
        f"Events: {summary['events']}  Users: {summary['users']}  Machines: {summary['machines']}  Sessions: {summary['sessions']}",
        f"Total Tokens: {summary['total_tokens']}  Effective: {summary['effective_tokens']}  Cached: {summary['cached_input_tokens']}",
    ]
    grouped = payload.get("grouped") or []
    if grouped:
        lines.append("")
        lines.append(f"Top by {payload['requested_group']}:")
        for row in grouped:
            lines.append(
                f"- {row['name']}: effective={row['effective_tokens']} total={row['tokens']} "
                f"events={row['events']} users={row['users']} machines={row['machines']}"
            )
    return "\n".join(lines)


def command_health(args) -> int:
    root = _resolve_team_log_root(args)
    files = _discover_team_files(root, args.team_id)
    payload = {
        "log_root": str(root),
        "team_id": args.team_id,
        "exists": root.exists(),
        "files": len(files),
        "sample_files": [str(path) for path in files[:3]],
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"log_root: {payload['log_root']}")
        print(f"exists:   {payload['exists']}")
        print(f"files:    {payload['files']}")
        if payload["sample_files"]:
            print("samples:")
            for item in payload["sample_files"]:
                print(f"  - {item}")
    return 0


def command_report(args) -> int:
    root = _resolve_team_log_root(args)
    window = build_time_window(today=args.today, last=args.last, start=args.start, end=args.end, tz_name=args.tz)
    events, files = _load_team_events(
        root,
        team_id=args.team_id,
        window=window,
        source_filter=args.source or [],
        user_filter=args.user or [],
    )
    payload = {
        "window": {
            "label": window.label,
            "start": window.start.isoformat() if window.start else None,
            "end": window.end.isoformat() if window.end else None,
            "timezone": window.timezone_name,
        },
        "summary": _summarize(events),
        "requested_group": args.by,
        "grouped": _group_rows(events, args.by, args.limit, window.timezone_name) if args.by else [],
        "files_scanned": len(files),
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render_report(payload))
    return 0


def _compute_event_id(team_id: str, user_id: str, machine_id: str, payload: dict[str, object]) -> str:
    raw = "|".join(
        [
            team_id,
            user_id,
            machine_id,
            str(payload.get("source")),
            str(payload.get("session_id")),
            str(payload.get("timestamp")),
            str(payload.get("raw_event_kind")),
            str(payload.get("total_tokens")),
            str(payload.get("source_path")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _load_local_collectors():
    repo_root = Path(__file__).resolve().parents[2]
    scripts_root = repo_root / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from adapters.claude_code import ClaudeCodeAdapter
    from adapters.codex import CodexAdapter
    from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter

    return {
        "codex": CodexAdapter,
        "claude-code": ClaudeCodeAdapter,
        "generic-openai-compatible": GenericOpenAICompatibleAdapter,
    }


def command_export_local(args) -> int:
    root = _resolve_team_log_root(args)
    window = build_time_window(today=args.today, last=args.last, start=args.start, end=args.end, tz_name=args.tz)
    registry = _load_local_collectors()
    selected_sources = args.source or list(registry.keys())

    exported_at = datetime.now().astimezone().isoformat()
    machine_id = args.machine_id or socket.gethostname()
    machine_label = args.machine_label or machine_id
    repo_root = Path(__file__).resolve().parents[2]
    scripts_root = repo_root / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from core.time_window import build_time_window as build_local_window

    local_window = build_local_window(
        today=args.today,
        last=args.last,
        start=args.start,
        end=args.end,
        tz_name=args.tz,
    )

    out_dir = root / args.team_id / "raw" / args.user_id / machine_id
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S.jsonl")
    output_path = out_dir / filename

    exported = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for source_id in selected_sources:
            adapter_cls = registry.get(source_id)
            if adapter_cls is None:
                raise SystemExit(f"unknown source for export-local: {source_id}")
            result = adapter_cls().collect(local_window)
            for event in result.events:
                payload = {
                    "team_id": args.team_id,
                    "user_id": args.user_id,
                    "machine_id": machine_id,
                    "machine_label": machine_label,
                    "source": event.source,
                    "provider": event.provider,
                    "model": event.model,
                    "session_id": event.session_id,
                    "project_path": event.project_path,
                    "timestamp": event.timestamp.isoformat(),
                    "input_tokens": event.input_tokens,
                    "cached_input_tokens": event.cached_input_tokens,
                    "output_tokens": event.output_tokens,
                    "reasoning_tokens": event.reasoning_tokens,
                    "total_tokens": event.total_tokens,
                    "accuracy_level": event.accuracy_level,
                    "raw_event_kind": event.raw_event_kind,
                    "source_path": event.source_path,
                    "exported_at": exported_at,
                }
                payload["event_id"] = _compute_event_id(args.team_id, args.user_id, machine_id, payload)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                exported += 1

    if args.format == "json":
        print(json.dumps({"output_path": str(output_path), "events_exported": exported, "window": window.label}, ensure_ascii=False, indent=2))
    else:
        print(f"output_path:     {output_path}")
        print(f"events_exported: {exported}")
        print(f"window:          {window.label}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Token Usage Universal Team Edition")
    parser.add_argument("--log-root", help=f"override {TEAM_LOG_ROOT_ENV}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_window_args(command):
        command.add_argument("--today", action="store_true", help="use local today window")
        command.add_argument("--last", help="relative window like 7d or 12h")
        command.add_argument("--start", help="custom window start in ISO format")
        command.add_argument("--end", help="custom window end in ISO format")
        command.add_argument("--tz", help="IANA timezone like US/Pacific")

    health = subparsers.add_parser("health", help="check shared team log root")
    health.add_argument("--team-id", help="restrict health scan to one team directory")
    health.add_argument("--format", choices=("ascii", "json"), default="ascii")
    health.set_defaults(func=command_health)

    report = subparsers.add_parser("report", help="build a team report from shared logs")
    add_window_args(report)
    report.add_argument("--team-id", required=True, help="team id to report")
    report.add_argument("--source", action="append", help="limit to one source")
    report.add_argument("--user", action="append", help="limit to one user")
    report.add_argument("--by", choices=("user", "machine", "project", "model", "source", "day"))
    report.add_argument("--limit", type=int, default=5, help="row limit per section")
    report.add_argument("--format", choices=("ascii", "json"), default="ascii")
    report.set_defaults(func=command_report)

    export_local = subparsers.add_parser("export-local", help="export local usage events to a shared team directory")
    add_window_args(export_local)
    export_local.add_argument("--team-id", required=True, help="team id to export under")
    export_local.add_argument("--user-id", required=True, help="stable user identifier")
    export_local.add_argument("--machine-id", help="stable machine identifier; defaults to hostname")
    export_local.add_argument("--machine-label", help="human-readable machine label")
    export_local.add_argument("--source", action="append", help="limit to one local source")
    export_local.add_argument("--format", choices=("ascii", "json"), default="ascii")
    export_local.set_defaults(func=command_export_local)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
