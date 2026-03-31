from __future__ import annotations

from datetime import datetime, timedelta

from core.models import TimeWindow, UsageEvent
from core.time_window import resolve_timezone


def day_key(timestamp: datetime, *, tz_name: str) -> str:
    tzinfo = resolve_timezone(tz_name)
    return timestamp.astimezone(tzinfo).strftime("%Y-%m-%d")


def split_window_days(window: TimeWindow) -> tuple[set[str], set[str]]:
    if not window.start or not window.end:
        return set(), set()

    tzinfo = resolve_timezone(window.timezone_name)
    start = window.start.astimezone(tzinfo)
    end = window.end.astimezone(tzinfo)
    cursor = datetime(start.year, start.month, start.day, tzinfo=tzinfo)
    last_day = datetime(end.year, end.month, end.day, tzinfo=tzinfo)
    full_days: set[str] = set()
    partial_days: set[str] = set()

    while cursor <= last_day:
        next_day = cursor + timedelta(days=1)
        key = cursor.strftime("%Y-%m-%d")
        if end >= cursor and start < next_day:
            if start <= cursor and end >= next_day:
                full_days.add(key)
            else:
                partial_days.add(key)
        cursor = next_day

    return full_days, partial_days


def build_day_rollups(events: list[UsageEvent], *, tz_name: str) -> list[UsageEvent]:
    grouped: dict[
        tuple[str, str, str, str, str | None, str | None, str | None, str, str | None, str],
        UsageEvent,
    ] = {}

    for event in events:
        key = (
            day_key(event.timestamp, tz_name=tz_name),
            event.source,
            event.provider,
            event.session_id,
            event.project_path,
            event.model,
            event.raw_model,
            event.model_resolution,
            event.model_source,
            event.accuracy_level,
        )
        current = grouped.get(key)
        if current is None:
            grouped[key] = UsageEvent(
                source=event.source,
                provider=event.provider,
                timestamp=event.timestamp,
                session_id=event.session_id,
                project_path=event.project_path,
                model=event.model,
                input_tokens=event.input_tokens or 0,
                cached_input_tokens=event.cached_input_tokens or 0,
                output_tokens=event.output_tokens or 0,
                reasoning_tokens=event.reasoning_tokens or 0,
                total_tokens=event.total_tokens,
                accuracy_level=event.accuracy_level,
                raw_event_kind="day_rollup",
                source_path=event.source_path,
                raw_model=event.raw_model,
                model_resolution=event.model_resolution,
                model_source=event.model_source,
            )
            continue

        grouped[key] = UsageEvent(
            source=current.source,
            provider=current.provider,
            timestamp=max(current.timestamp, event.timestamp),
            session_id=current.session_id,
            project_path=current.project_path,
            model=current.model,
            input_tokens=(current.input_tokens or 0) + (event.input_tokens or 0),
            cached_input_tokens=(current.cached_input_tokens or 0) + (event.cached_input_tokens or 0),
            output_tokens=(current.output_tokens or 0) + (event.output_tokens or 0),
            reasoning_tokens=(current.reasoning_tokens or 0) + (event.reasoning_tokens or 0),
            total_tokens=current.total_tokens + event.total_tokens,
            accuracy_level=current.accuracy_level,
            raw_event_kind="day_rollup",
            source_path=current.source_path,
            raw_model=current.raw_model,
            model_resolution=current.model_resolution,
            model_source=current.model_source,
        )

    return sorted(grouped.values(), key=lambda item: item.timestamp)
