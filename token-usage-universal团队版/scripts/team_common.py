#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class TimeWindow:
    start: datetime | None
    end: datetime | None
    label: str
    timezone_name: str


def resolve_tz(name: str | None):
    if name:
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name)
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"invalid timezone: {name}") from exc
    return datetime.now().astimezone().tzinfo


def coerce_datetime(value: str, tz_name: str | None) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=resolve_tz(tz_name))
    return parsed


def parse_last(value: str) -> timedelta:
    if value.endswith("d"):
        return timedelta(days=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    raise SystemExit(f"unsupported --last value: {value}")


def build_time_window(*, today: bool, last: str | None, start: str | None, end: str | None, tz_name: str | None, default_mode: str = "today") -> TimeWindow:
    tzinfo = resolve_tz(tz_name)
    now = datetime.now(tzinfo)

    if start or end:
        start_dt = coerce_datetime(start, tz_name).astimezone(tzinfo) if start else None
        end_dt = coerce_datetime(end, tz_name).astimezone(tzinfo) if end else now
        return TimeWindow(start=start_dt, end=end_dt, label="custom", timezone_name=str(tzinfo))

    if last:
        duration = parse_last(last)
        return TimeWindow(start=now - duration, end=now, label=f"last {last}", timezone_name=str(tzinfo))

    if today or default_mode == "today":
        day_start = datetime(now.year, now.month, now.day, tzinfo=tzinfo)
        return TimeWindow(start=day_start, end=now, label="today", timezone_name=str(tzinfo))

    if default_mode.startswith("last:"):
        duration = parse_last(default_mode.split(":", 1)[1])
        return TimeWindow(start=now - duration, end=now, label=default_mode.replace(":", " "), timezone_name=str(tzinfo))

    return TimeWindow(start=None, end=None, label="all", timezone_name=str(tzinfo))


def within_window(window: TimeWindow, timestamp: datetime) -> bool:
    if window.start and timestamp < window.start:
        return False
    if window.end and timestamp > window.end:
        return False
    return True


def effective_tokens(total_tokens: int, cached_input_tokens: int | None) -> int:
    return max(int(total_tokens) - int(cached_input_tokens or 0), 0)


def compute_event_id(team_id: str, user_id: str, machine_id: str, payload: dict[str, object]) -> str:
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
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_local_collectors():
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


def build_local_window(*, today: bool, last: str | None, start: str | None, end: str | None, tz_name: str | None):
    repo_root = Path(__file__).resolve().parents[2]
    scripts_root = repo_root / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    from core.time_window import build_time_window as build_source_window

    return build_source_window(today=today, last=last, start=start, end=end, tz_name=tz_name)


def build_ingest_event(event, *, team_id: str, user_id: str, machine_id: str, machine_label: str, exported_at: str) -> dict[str, object]:
    payload = {
        "team_id": team_id,
        "user_id": user_id,
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
    payload["event_id"] = compute_event_id(team_id, user_id, machine_id, payload)
    return payload
