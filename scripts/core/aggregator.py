from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from core.models import SourceCollectResult, TimeWindow, UsageEvent
from core.pricing import PricingDatabase
from core.time_window import resolve_timezone


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "effective_tokens",
)


def _blank_totals() -> dict[str, int]:
    return {field: 0 for field in TOKEN_FIELDS}


def _effective_tokens(*, cached_input_tokens: int | None, total_tokens: int | None) -> int:
    return max(0, int(total_tokens or 0) - int(cached_input_tokens or 0))


def _add_event_totals(totals: dict[str, int], event: UsageEvent) -> None:
    totals["input_tokens"] += event.input_tokens or 0
    totals["cached_input_tokens"] += event.cached_input_tokens or 0
    totals["output_tokens"] += event.output_tokens or 0
    totals["reasoning_tokens"] += event.reasoning_tokens or 0
    totals["total_tokens"] += event.total_tokens
    totals["effective_tokens"] += _effective_tokens(
        cached_input_tokens=event.cached_input_tokens,
        total_tokens=event.total_tokens,
    )


def _has_breakdown(event: UsageEvent) -> bool:
    return any(
        value is not None
        for value in (
            event.input_tokens,
            event.cached_input_tokens,
            event.output_tokens,
            event.reasoning_tokens,
        )
    )


def _window_days(window: TimeWindow) -> float:
    if window.start and window.end:
        total_seconds = max(0.0, (window.end - window.start).total_seconds())
        if total_seconds >= 86_400:
            return total_seconds / 86_400
    return 1.0


def _event_cost(event: UsageEvent, pricing: PricingDatabase) -> tuple[float, bool]:
    estimated = pricing.estimate_cost(
        model=event.model,
        provider=event.provider,
        input_tokens=event.input_tokens,
        cached_input_tokens=event.cached_input_tokens,
        output_tokens=event.output_tokens,
        reasoning_tokens=event.reasoning_tokens,
        total_tokens=event.total_tokens,
    )
    if estimated is None:
        return 0.0, True
    return estimated, False


def _annotate_events(events: list[UsageEvent], pricing: PricingDatabase) -> tuple[list[dict[str, object]], bool]:
    annotated: list[dict[str, object]] = []
    has_missing_cost = False
    for event in events:
        estimated_cost, missing_cost = _event_cost(event, pricing)
        has_missing_cost = has_missing_cost or missing_cost
        annotated.append(
            {
                "event": event,
                "estimated_cost_usd": estimated_cost,
            }
        )
    return annotated, has_missing_cost


def _resolve_tzinfo(name: str):
    return resolve_timezone(name)


def _model_resolution_rank(value: str | None) -> int:
    return {
        "unknown": 0,
        "alias": 1,
        "inferred": 2,
        "exact": 3,
    }.get(str(value or "unknown"), 0)


def _pick_model_meta(current: dict[str, object], event: UsageEvent) -> dict[str, object]:
    event_rank = _model_resolution_rank(event.model_resolution)
    current_rank = _model_resolution_rank(current.get("model_resolution"))
    if event_rank > current_rank:
        return {
            "model": event.model,
            "raw_model": event.raw_model,
            "model_resolution": event.model_resolution,
            "model_source": event.model_source,
        }
    if event_rank == current_rank and event.model_source == "turn_context":
        return {
            "model": event.model,
            "raw_model": event.raw_model,
            "model_resolution": event.model_resolution,
            "model_source": event.model_source,
        }
    return current


def _group_events(annotated_events: list[dict[str, object]], key_name: str, *, limit: int) -> list[dict[str, object]]:
    grouped_totals: dict[str, dict[str, int]] = defaultdict(_blank_totals)
    grouped_sessions: dict[str, set[str]] = defaultdict(set)
    grouped_models: dict[str, set[str]] = defaultdict(set)
    grouped_costs: dict[str, float] = defaultdict(float)
    grouped_timestamps: dict[str, datetime] = {}
    grouped_meta: dict[str, dict[str, object]] = {}

    for item in annotated_events:
        event = item["event"]
        if key_name == "source":
            name = event.source
        elif key_name == "model":
            name = event.model or "(unknown model)"
        elif key_name == "project":
            name = event.project_path or "(unknown project)"
        elif key_name == "session":
            name = event.session_id
        else:
            raise ValueError(f"unsupported group key: {key_name}")

        _add_event_totals(grouped_totals[name], event)
        grouped_sessions[name].add(event.session_id)
        grouped_models[name].add(event.model or "(unknown model)")
        grouped_costs[name] += float(item["estimated_cost_usd"])
        grouped_timestamps[name] = max(grouped_timestamps.get(name, event.timestamp), event.timestamp)

        meta = grouped_meta.setdefault(
            name,
            {
                "project_path": event.project_path,
                "model": event.model,
                "raw_model": event.raw_model,
                "model_resolution": event.model_resolution,
                "model_source": event.model_source,
                "source": event.source,
            },
        )
        if not meta.get("project_path") and event.project_path:
            meta["project_path"] = event.project_path
        if event.model:
            updated_meta = _pick_model_meta(meta, event)
            meta["model"] = updated_meta["model"]
            meta["raw_model"] = updated_meta["raw_model"]
            meta["model_resolution"] = updated_meta["model_resolution"]
            meta["model_source"] = updated_meta["model_source"]

    rows: list[dict[str, object]] = []
    for name, totals in grouped_totals.items():
        row = {
            "name": name,
            **totals,
            "sessions": len(grouped_sessions[name]),
            "models": len(grouped_models[name]),
            "estimated_cost_usd": round(grouped_costs[name], 6),
            "last_timestamp": grouped_timestamps[name].isoformat(),
            **grouped_meta[name],
        }
        rows.append(row)

    rows.sort(key=lambda item: (item["effective_tokens"], item["total_tokens"], item["input_tokens"]), reverse=True)
    return rows[:limit]


def _group_by_day(annotated_events: list[dict[str, object]], *, tz_name: str, limit: int | None = None) -> list[dict[str, object]]:
    tzinfo = _resolve_tzinfo(tz_name)
    grouped_totals: dict[str, dict[str, int]] = defaultdict(_blank_totals)
    grouped_sessions: dict[str, set[str]] = defaultdict(set)
    grouped_models: dict[str, set[str]] = defaultdict(set)
    grouped_costs: dict[str, float] = defaultdict(float)

    for item in annotated_events:
        event = item["event"]
        day_key = event.timestamp.astimezone(tzinfo).strftime("%Y-%m-%d")
        _add_event_totals(grouped_totals[day_key], event)
        grouped_sessions[day_key].add(event.session_id)
        grouped_models[day_key].add(event.model or "(unknown model)")
        grouped_costs[day_key] += float(item["estimated_cost_usd"])

    rows = [
        {
            "date": day_key,
            **grouped_totals[day_key],
            "sessions": len(grouped_sessions[day_key]),
            "models": len(grouped_models[day_key]),
            "estimated_cost_usd": round(grouped_costs[day_key], 6),
        }
        for day_key in sorted(grouped_totals.keys())
    ]
    if limit is not None:
        return rows[-limit:]
    return rows


def _select_current_session(annotated_events: list[dict[str, object]]) -> dict[str, object] | None:
    if not annotated_events:
        return None
    sessions = _group_events(annotated_events, "session", limit=max(1, len(annotated_events)))
    if not sessions:
        return None
    sessions.sort(key=lambda row: (row["last_timestamp"], row["effective_tokens"], row["total_tokens"]), reverse=True)
    current = sessions[0]
    total_tokens = int(current["total_tokens"])
    current["events"] = sum(1 for item in annotated_events if item["event"].session_id == current["name"])
    current["session_id"] = current["name"]
    current["cache_ratio"] = (int(current["cached_input_tokens"]) / total_tokens) if total_tokens else 0.0
    return current


def _build_session_detail(annotated_events: list[dict[str, object]], session_id: str) -> dict[str, object] | None:
    matches = [item for item in annotated_events if item["event"].session_id == session_id]
    if not matches:
        return None
    detail = _group_events(matches, "session", limit=1)[0]
    detail["events"] = len(matches)
    detail["session_id"] = session_id
    total_tokens = int(detail["total_tokens"])
    detail["cache_ratio"] = (int(detail["cached_input_tokens"]) / total_tokens) if total_tokens else 0.0
    return detail


def _build_trend(
    by_day: list[dict[str, object]],
    days: int,
    *,
    tz_name: str,
    reference_end: datetime | None,
) -> dict[str, object]:
    tzinfo = _resolve_tzinfo(tz_name)
    anchor = (reference_end or datetime.now(tzinfo)).astimezone(tzinfo)
    by_date = {item["date"]: item for item in by_day}
    start_day = anchor.date() - timedelta(days=days - 1)
    points: list[dict[str, object]] = []

    for index in range(days):
        current_day = start_day + timedelta(days=index)
        key = current_day.strftime("%Y-%m-%d")
        points.append(
            by_date.get(
                key,
                {
                    "date": key,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                    "effective_tokens": 0,
                    "sessions": 0,
                    "models": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
        )

    totals = [int(item["effective_tokens"]) for item in points]
    avg = int(sum(totals) / len(totals)) if totals else 0
    return {
        "days": days,
        "points": points,
        "total_tokens": sum(totals),
        "min_tokens": min(totals) if totals else 0,
        "max_tokens": max(totals) if totals else 0,
        "avg_tokens": avg,
        "latest_tokens": totals[-1] if totals else 0,
        "estimated_cost_usd": round(sum(float(item["estimated_cost_usd"]) for item in points), 6),
    }


def _month_key(value: datetime) -> str:
    return value.strftime("%Y-%m")


def _build_calendar_month(
    by_day: list[dict[str, object]],
    *,
    tz_name: str,
    requested_month: str | None,
    reference_end: datetime | None,
) -> dict[str, object]:
    tzinfo = _resolve_tzinfo(tz_name)
    if requested_month:
        anchor = datetime.strptime(requested_month, "%Y-%m").replace(tzinfo=tzinfo)
    else:
        anchor = (reference_end or datetime.now(tzinfo)).astimezone(tzinfo)
    first_day = datetime(anchor.year, anchor.month, 1, tzinfo=tzinfo)
    if anchor.month == 12:
        next_month = datetime(anchor.year + 1, 1, 1, tzinfo=tzinfo)
    else:
        next_month = datetime(anchor.year, anchor.month + 1, 1, tzinfo=tzinfo)

    by_date = {item["date"]: item for item in by_day}
    rows: list[dict[str, object]] = []
    cursor = first_day
    while cursor < next_month:
        key = cursor.strftime("%Y-%m-%d")
        rows.append(
            by_date.get(
                key,
                {
                    "date": key,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                    "effective_tokens": 0,
                    "sessions": 0,
                    "models": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
        )
        cursor += timedelta(days=1)

    return {
        "month": _month_key(first_day),
        "days": rows,
        "total_tokens": sum(int(item["total_tokens"]) for item in rows),
        "effective_tokens": sum(int(item["effective_tokens"]) for item in rows),
        "avg_tokens": int(sum(int(item["effective_tokens"]) for item in rows) / len(rows)) if rows else 0,
        "max_tokens": max((int(item["effective_tokens"]) for item in rows), default=0),
        "estimated_cost_usd": round(sum(float(item["estimated_cost_usd"]) for item in rows), 6),
    }


def _extract_observed_only_models(results: list[SourceCollectResult]) -> list[dict[str, object]]:
    exact_models = {
        (event.model or "").strip().lower()
        for result in results
        for event in result.events
        if event.model
    }
    observed: dict[str, set[str]] = defaultdict(set)

    for result in results:
        for detail in result.detection.details:
            prefix = "detected model traces in desktop stores:"
            if not detail.lower().startswith(prefix):
                continue
            raw_models = detail.split(":", 1)[1] if ":" in detail else ""
            for raw_model in raw_models.split(","):
                model = raw_model.strip()
                if not model:
                    continue
                if model.lower() in exact_models:
                    continue
                observed[model].add(result.detection.source_id)

    return [
        {
            "name": model,
            "sources": sorted(sources),
            "evidence": "model-trace-only",
        }
        for model, sources in sorted(observed.items())
    ]


def _extract_observed_only_sources(results: list[SourceCollectResult]) -> list[dict[str, object]]:
    observed_sources: list[dict[str, object]] = []
    for result in results:
        if result.events:
            continue
        detection = result.detection
        summary = detection.summary.lower()
        if "traces detected" not in summary and "decoded" not in summary:
            continue
        observed_sources.append(
            {
                "source_id": detection.source_id,
                "display_name": detection.display_name,
                "reason": detection.summary,
                "files": result.scanned_files,
            }
        )
    return observed_sources


def build_report(
    results: list[SourceCollectResult],
    *,
    window: TimeWindow,
    group_by: str | None,
    limit: int,
    trend: str | None = None,
    calendar: str | None = None,
    calendar_month: str | None = None,
    session_id: str | None = None,
    chart_results: list[SourceCollectResult] | None = None,
    dashboard_mode: str | None = None,
) -> dict[str, object]:
    pricing = PricingDatabase()
    events = [event for result in results for event in result.events]
    annotated_events, has_missing_cost = _annotate_events(events, pricing)
    chart_events = [event for result in (chart_results or results) for event in result.events]
    annotated_chart_events, _ = _annotate_events(chart_events, pricing)

    totals = _blank_totals()
    source_sessions: set[str] = set()
    for event in events:
        _add_event_totals(totals, event)
        source_sessions.add(event.session_id)

    status_counts = {"exact": 0, "derived": 0, "estimated": 0, "unsupported": 0}
    diagnostics: list[dict[str, str]] = []
    seen_diagnostics: set[tuple[str, str]] = set()

    for result in results:
        detection = result.detection
        if detection.supported and detection.available:
            status_counts[detection.accuracy_level] += 1
        else:
            status_counts["unsupported"] += 1

        if not result.events:
            pair = (detection.source_id, detection.summary)
            if pair not in seen_diagnostics:
                diagnostics.append({"source": detection.source_id, "reason": detection.summary})
                seen_diagnostics.add(pair)

        for message in result.verification_issues + result.skipped_reasons:
            pair = (detection.source_id, message)
            if pair not in seen_diagnostics:
                diagnostics.append({"source": detection.source_id, "reason": message})
                seen_diagnostics.add(pair)

    estimated_total = round(sum(float(item["estimated_cost_usd"]) for item in annotated_events), 6)
    if has_missing_cost and events:
        pair = ("estimated-cost", "estimated cost incomplete for one or more events")
        if pair not in seen_diagnostics:
            diagnostics.append({"source": pair[0], "reason": pair[1]})

    summary = {
        **totals,
        "sources": len({event.source for event in events}),
        "models": len({event.model or "(unknown model)" for event in events}),
        "sessions": len(source_sessions),
        "events": len(events),
        "split_detail_events": sum(1 for event in events if _has_breakdown(event)),
        "total_only_events": sum(1 for event in events if not _has_breakdown(event)),
        "estimated_cost_usd": estimated_total,
        "cost_accuracy": "estimated" if estimated_total or events else "unavailable",
    }
    observed_only_sources = _extract_observed_only_sources(results)
    observed_only_models = _extract_observed_only_models(results)
    summary["observed_only_sources"] = len(observed_only_sources)
    summary["observed_only_models"] = len(observed_only_models)

    by_day = _group_by_day(annotated_events, tz_name=window.timezone_name)
    chart_by_day = _group_by_day(annotated_chart_events, tz_name=window.timezone_name)
    report = {
        "window": {
            **window.as_dict(),
            "timezone": window.timezone_name,
            "days_equivalent": round(_window_days(window), 2),
        },
        "summary": summary,
        "status_counts": status_counts,
        "by_source": _group_events(annotated_events, "source", limit=limit),
        "by_model": _group_events(annotated_events, "model", limit=limit),
        "by_project": _group_events(annotated_events, "project", limit=limit),
        "by_session": _group_events(annotated_events, "session", limit=limit),
        "by_day": by_day[-limit:] if group_by == "day" else by_day,
        "current_session": _select_current_session(annotated_events),
        "session_detail": _build_session_detail(annotated_events, session_id) if session_id else None,
        "observed_only_sources": observed_only_sources,
        "observed_only_models": observed_only_models,
        "diagnostics": diagnostics[: max(limit, 10)],
        "requested_group": group_by,
        "requested_trend": trend,
        "requested_calendar": calendar,
        "requested_session_id": session_id,
        "dashboard_mode": dashboard_mode,
        "charts": {
            "trend_7d": _build_trend(
                chart_by_day,
                7,
                tz_name=window.timezone_name,
                reference_end=window.end,
            ),
            "trend_30d": _build_trend(
                chart_by_day,
                30,
                tz_name=window.timezone_name,
                reference_end=window.end,
            ),
            "calendar_month": _build_calendar_month(
                chart_by_day,
                tz_name=window.timezone_name,
                requested_month=calendar_month,
                reference_end=window.end,
            ),
        },
    }
    return report
