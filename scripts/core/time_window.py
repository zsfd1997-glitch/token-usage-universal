from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.models import TimeWindow


_DURATION_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[dh])$")
_TIMEZONE_FALLBACKS = {
    "US/Pacific": ("America/Los_Angeles",),
    "US/Mountain": ("America/Denver",),
    "US/Central": ("America/Chicago",),
    "US/Eastern": ("America/New_York",),
    "US/Alaska": ("America/Anchorage",),
    "US/Hawaii": ("Pacific/Honolulu",),
}


def _timezone_candidates(name: str) -> tuple[str, ...]:
    fallbacks = tuple(candidate for candidate in _TIMEZONE_FALLBACKS.get(name, ()) if candidate != name)
    return (name, *fallbacks)


def resolve_timezone(name: str | None):
    if name:
        last_error: ZoneInfoNotFoundError | None = None
        for candidate in _timezone_candidates(name):
            try:
                return ZoneInfo(candidate)
            except ZoneInfoNotFoundError as exc:
                last_error = exc
        local_tz = datetime.now().astimezone().tzinfo
        local_candidates = {
            name,
            *(candidate for candidate in _TIMEZONE_FALLBACKS.get(name, ())),
        }
        if local_tz and (datetime.now(local_tz).tzname() in local_candidates or getattr(local_tz, "key", None) in local_candidates):
            return local_tz
        raise ValueError(f"unknown timezone: {name}") from last_error
    return datetime.now().astimezone().tzinfo


def timezone_name(tzinfo) -> str:
    key = getattr(tzinfo, "key", None)
    if key:
        return key
    return datetime.now(tzinfo).tzname() or "local"


def parse_timestamp(value: str, tzinfo):
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tzinfo)
    return parsed.astimezone(tzinfo)


def build_time_window(
    *,
    today: bool,
    last: str | None,
    start: str | None,
    end: str | None,
    tz_name: str | None,
) -> TimeWindow:
    tzinfo = resolve_timezone(tz_name)
    now = datetime.now(tzinfo)
    tz_label = now.tzname() or timezone_name(tzinfo)
    tz_storage_name = tz_name or timezone_name(tzinfo)

    selected = sum(bool(item) for item in (today, last, start or end))
    if selected > 1:
        raise ValueError("choose only one of --today, --last, or --start/--end")

    if today or selected == 0:
        start_dt = datetime(now.year, now.month, now.day, tzinfo=tzinfo)
        return TimeWindow(
            start=start_dt,
            end=now,
            label=f"Today ({now.strftime('%Y-%m-%d')} {tz_label})",
            timezone_name=tz_storage_name,
        )

    if last:
        match = _DURATION_RE.match(last)
        if not match:
            raise ValueError("invalid --last value, use forms like 7d or 12h")
        value = int(match.group("value"))
        unit = match.group("unit")
        delta = timedelta(days=value) if unit == "d" else timedelta(hours=value)
        start_dt = now - delta
        return TimeWindow(
            start=start_dt,
            end=now,
            label=f"Last {last} ending {now.strftime('%Y-%m-%d %H:%M')} {tz_label}",
            timezone_name=tz_storage_name,
        )

    start_dt = parse_timestamp(start, tzinfo) if start else None
    end_dt = parse_timestamp(end, tzinfo) if end else now
    return TimeWindow(
        start=start_dt,
        end=end_dt,
        label=f"Custom ({(start_dt or end_dt).strftime('%Y-%m-%d %H:%M')} -> {end_dt.strftime('%Y-%m-%d %H:%M')} {tz_label})",
        timezone_name=tz_storage_name,
    )


def build_month_window(year_month: str | None, tz_name: str | None) -> TimeWindow:
    tzinfo = resolve_timezone(tz_name)
    now = datetime.now(tzinfo)
    tz_label = now.tzname() or timezone_name(tzinfo)
    tz_storage_name = tz_name or timezone_name(tzinfo)

    if year_month:
        try:
            anchor = datetime.strptime(year_month, "%Y-%m").replace(tzinfo=tzinfo)
        except ValueError as exc:
            raise ValueError("invalid --month value, use YYYY-MM") from exc
    else:
        anchor = datetime(now.year, now.month, 1, tzinfo=tzinfo)

    start_dt = datetime(anchor.year, anchor.month, 1, tzinfo=tzinfo)
    if anchor.month == 12:
        next_month = datetime(anchor.year + 1, 1, 1, tzinfo=tzinfo)
    else:
        next_month = datetime(anchor.year, anchor.month + 1, 1, tzinfo=tzinfo)

    end_dt = min(next_month, now) if start_dt <= now < next_month else next_month
    return TimeWindow(
        start=start_dt,
        end=end_dt,
        label=f"Month ({start_dt.strftime('%Y-%m')} {tz_label})",
        timezone_name=tz_storage_name,
    )


def within_window(window: TimeWindow, timestamp: datetime) -> bool:
    if window.start and timestamp < window.start:
        return False
    if window.end and timestamp > window.end:
        return False
    return True
