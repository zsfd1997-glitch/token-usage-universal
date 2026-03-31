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

MODEL_ANCHOR_OPENAI = "OpenAI GPT-5.3-Codex / GPT-5.4"
MODEL_ANCHOR_ANTHROPIC = "Anthropic Opus 4.5 / Opus 4.6"
MODEL_ANCHOR_VERIFIED_AT = "2026-03-25"

REALMS = [
    {
        "name": "练气",
        "label": "基础辅助",
        "min": 0,
        "max": 10_000_000,
        "role_anchor": "初级工程师 / 普通员工",
        "team_anchor": "轻量、日常、基础辅助",
        "model_reference": "Claude Code Sonnet 4.6 常规使用",
        "reference_note": "Anthropic 官方 Claude Code 成本页以 Sonnet 4.6 口径说明：平均每位开发者每天约 $6，90% 低于 $12。",
        "business_suggestion": "先把 AI 固定纳入查询、拆解和轻量编码，重点是形成稳定使用习惯。",
        "business_comment": "当前仍是基础辅助强度，适合把 AI 当作持续在线的工程助手。",
    },
    {
        "name": "筑基",
        "label": "稳定使用",
        "min": 10_000_000,
        "max": 100_000_000,
        "role_anchor": "中级工程师",
        "team_anchor": "稳定进入工程主流程",
        "model_reference": "Claude Opus 4.5 / Sonnet 4.6 高频使用",
        "reference_note": "Anthropic 团队使用建议显示，小团队通常按每人 200k-300k TPM 预留，说明高频工程接入已是官方默认场景。",
        "business_suggestion": "继续把 token 投到排障、补测、重构和需求拆解上，让 AI 真正进入主流程。",
        "business_comment": "当前已进入稳定使用强度，AI 可以成为日常工程流程的一部分。",
    },
    {
        "name": "金丹",
        "label": "高强度生产",
        "min": 100_000_000,
        "max": 500_000_000,
        "role_anchor": "资深工程师",
        "team_anchor": "高强度个人生产",
        "model_reference": "GPT-5.3-Codex / Claude Opus 4.6",
        "reference_note": "以 GPT-5.3-Codex 与 Claude Opus 4.6 为高强度个人生产锚点，适合持续编码、测试、重构和方案比对。",
        "business_suggestion": "适合把 AI 用在完整需求闭环里，让编码、验证和修复都保持高频并行。",
        "business_comment": "当前已进入资深工程师对应的高强度个人生产区间。",
    },
    {
        "name": "元婴",
        "label": "规模化交付",
        "min": 500_000_000,
        "max": 2_000_000_000,
        "role_anchor": "Staff / Tech Lead",
        "team_anchor": "多线程、高密度交付",
        "model_reference": "GPT-5.4 / Claude Opus 4.6 多线工作流",
        "reference_note": "OpenAI 官方于 2026-03-05 发布 GPT-5.4 并已进入 Codex；Anthropic 官方案例显示，Rakuten 用 Claude Code 实现过 7 小时持续自治编码。",
        "business_suggestion": "适合把 AI 编进多线程任务流、并行实验和跨项目交付，追求整体吞吐而不是单点省 token。",
        "business_comment": "当前已进入 Staff / Tech Lead 常见的多线程交付区间。",
    },
    {
        "name": "化神",
        "label": "战略级火力",
        "min": 2_000_000_000,
        "max": None,
        "role_anchor": "Principal / AI 平台负责人",
        "team_anchor": "平台级、组织级火力",
        "model_reference": "GPT-5.4 + 公司级 Claude Code / agent 编排",
        "reference_note": "OpenAI 企业 AI 报告显示，已有 9,000+ 组织处理过 100 亿+ tokens，近 200 家超过 1 万亿；这个等级更接近组织级配置，而不是个人勤奋。",
        "business_suggestion": "适合用平台化编排、agent 队列和治理体系承接 token 吞吐，重点是组织级效率。",
        "business_comment": "当前已接近公司级、平台级 AI 工程火力。",
    },
]

SENIOR_BAND = (100_000_000, 500_000_000)

BENCHMARK_EXAMPLES = [
    {
        "vendor": "OpenAI",
        "source_name": "Introducing GPT-5.4",
        "source_url": "https://openai.com/index/introducing-gpt-5-4/",
        "event_date": "2026-03-05",
        "evidence_type": "direct_fact",
        "fact": "GPT-5.4 rolled out across ChatGPT, the API, and Codex, and incorporates the frontier coding capabilities of GPT-5.3-Codex.",
    },
    {
        "vendor": "OpenAI",
        "source_name": "The state of enterprise AI 2025 report",
        "source_url": "https://openai.com/business/guides-and-resources/the-state-of-enterprise-ai-2025-report/",
        "event_date": "2025 report",
        "evidence_type": "direct_fact",
        "fact": "More than 9,000 organizations have processed over 10 billion tokens, and nearly 200 have exceeded 1 trillion tokens.",
    },
    {
        "vendor": "OpenAI",
        "source_name": "Codex is now generally available",
        "source_url": "https://openai.com/index/codex-now-generally-available/",
        "event_date": "2025-10-06",
        "evidence_type": "direct_fact",
        "fact": "Inside OpenAI, nearly all engineers use Codex, and GPT-5-Codex served over 40 trillion tokens in the three weeks since launch.",
    },
    {
        "vendor": "Anthropic",
        "source_name": "Manage costs effectively",
        "source_url": "https://code.claude.com/docs/en/costs",
        "event_date": "accessed 2026-03-25",
        "evidence_type": "direct_fact",
        "fact": "Claude Code averages about $6 per developer per day, with 90% of users below $12 per day, and the page uses Sonnet 4.6 as its cost anchor.",
    },
    {
        "vendor": "Anthropic",
        "source_name": "Manage costs effectively",
        "source_url": "https://code.claude.com/docs/en/costs",
        "event_date": "accessed 2026-03-25",
        "evidence_type": "direct_fact",
        "fact": "Anthropic recommends 200k-300k TPM per user for 1-5 user teams and 10k-15k TPM per user for 500+ user teams.",
    },
    {
        "vendor": "Anthropic",
        "source_name": "Models overview",
        "source_url": "https://platform.claude.com/docs/en/about-claude/models/overview",
        "event_date": "accessed 2026-03-25",
        "evidence_type": "direct_fact",
        "fact": "Latest models comparison lists Claude Opus 4.6, Claude Sonnet 4.6, and Claude Haiku 4.5, and positions Opus 4.6 as the latest generation model for coding and reasoning.",
    },
    {
        "vendor": "Anthropic",
        "source_name": "Model system cards",
        "source_url": "https://www.anthropic.com/system-cards/",
        "event_date": "2026-02 / 2025-11",
        "evidence_type": "direct_fact",
        "fact": "Anthropic publicly lists Claude Opus 4.6 system cards for February 2026 and Claude Opus 4.5 system cards for November 2025.",
    },
    {
        "vendor": "Anthropic",
        "source_name": "Rakuten customer story",
        "source_url": "https://claude.com/customers/rakuten",
        "event_date": "accessed 2026-03-25",
        "evidence_type": "direct_fact",
        "fact": "Rakuten reports 7 hours of sustained autonomous coding with Claude Code and a 79% reduction in time to market.",
    },
]


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


def _format_compact(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _band_label(start: int, end: int | None) -> str:
    if end is None:
        return f"{_format_compact(start)}+ / day"
    return f"{_format_compact(start)} - {_format_compact(end)} / day"


def _build_meter(progress_ratio: float, width: int = 24) -> str:
    clamped = max(0.0, min(1.0, progress_ratio))
    filled = width if clamped >= 1.0 else int(clamped * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def _window_days(window: TimeWindow) -> float:
    if window.start and window.end:
        total_seconds = max(0.0, (window.end - window.start).total_seconds())
        if total_seconds >= 86_400:
            return total_seconds / 86_400
    return 1.0


def _select_realm(daily_equivalent_tokens: int) -> dict[str, object]:
    current = REALMS[0]
    for realm in REALMS:
        if daily_equivalent_tokens >= realm["min"]:
            current = realm
        else:
            break
    return current


def _build_comment(realm: dict[str, object], cache_ratio: float) -> str:
    comment = str(realm["business_comment"])
    if cache_ratio >= 0.75:
        return comment + " 上下文复用效率也比较高。"
    return comment


def _build_insights(summary: dict[str, int | float | str], *, window: TimeWindow) -> dict[str, object]:
    total_tokens = int(summary["total_tokens"])
    input_tokens = int(summary["input_tokens"])
    cached_input_tokens = int(summary["cached_input_tokens"])
    sessions = int(summary["sessions"])
    events = int(summary["events"])
    days_equivalent = _window_days(window)
    daily_equivalent_tokens = int(total_tokens / days_equivalent) if total_tokens else 0

    current_realm = _select_realm(daily_equivalent_tokens)
    current_index = REALMS.index(current_realm)
    next_realm = REALMS[current_index + 1] if current_index + 1 < len(REALMS) else None

    current_floor = int(current_realm["min"])
    current_ceiling = current_realm["max"]
    if current_ceiling is None:
        progress_ratio = 1.0
        tokens_to_next_realm = 0
        next_target = "最高等级"
        next_realm_name = "已达最高等级"
    else:
        segment_size = max(1, int(current_ceiling) - current_floor)
        progress_ratio = (daily_equivalent_tokens - current_floor) / segment_size
        tokens_to_next_realm = max(0, int(current_ceiling) - daily_equivalent_tokens)
        next_target = _format_compact(int(current_ceiling))
        next_realm_name = str(next_realm["name"]) if next_realm else "已达最高等级"

    cache_ratio = (cached_input_tokens / input_tokens) if input_tokens else 0.0
    avg_per_session = int(total_tokens / sessions) if sessions else total_tokens
    avg_per_event = int(total_tokens / events) if events else total_tokens
    business_comment = _build_comment(current_realm, cache_ratio)

    return {
        "realm_name": current_realm["name"],
        "realm_label": current_realm["label"],
        "realm_band": _band_label(current_floor, current_ceiling),
        "next_realm_name": next_realm_name,
        "tokens_to_next_realm": tokens_to_next_realm,
        "progress_ratio": progress_ratio,
        "meter": _build_meter(progress_ratio),
        "daily_equivalent_tokens": daily_equivalent_tokens,
        "window_days_equivalent": round(days_equivalent, 2),
        "role_anchor": current_realm["role_anchor"],
        "team_anchor": current_realm["team_anchor"],
        "model_reference": current_realm["model_reference"],
        "reference_note": current_realm["reference_note"],
        "business_comment": business_comment,
        "business_suggestion": current_realm["business_suggestion"],
        "model_anchor_openai": MODEL_ANCHOR_OPENAI,
        "model_anchor_anthropic": MODEL_ANCHOR_ANTHROPIC,
        "model_anchor_verified_at": MODEL_ANCHOR_VERIFIED_AT,
        "tokens_to_next": tokens_to_next_realm,
        "next_target": next_target,
        "next_title": next_realm_name,
        "senior_band": _band_label(SENIOR_BAND[0], SENIOR_BAND[1]),
        "verdict": business_comment,
        "nudge": current_realm["business_suggestion"],
        "cache_ratio": cache_ratio,
        "avg_per_session": avg_per_session,
        "avg_per_event": avg_per_event,
        "compact_total": _format_compact(total_tokens),
        "compact_daily_equivalent": _format_compact(daily_equivalent_tokens),
        "compact_to_next": _format_compact(tokens_to_next_realm),
        "compact_to_next_realm": _format_compact(tokens_to_next_realm),
        "level_code": current_realm["name"],
        "level_title": current_realm["label"],
        "level_band": _band_label(current_floor, current_ceiling),
    }


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
        "diagnostics": diagnostics[: max(limit, 10)],
        "benchmark_examples": BENCHMARK_EXAMPLES,
        "insights": _build_insights(summary, window=window),
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
