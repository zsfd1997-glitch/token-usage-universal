from __future__ import annotations

from collections import defaultdict

from core.models import SourceCollectResult, TimeWindow, UsageEvent


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
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


def _add_event_totals(totals: dict[str, int], event: UsageEvent) -> None:
    totals["input_tokens"] += event.input_tokens or 0
    totals["cached_input_tokens"] += event.cached_input_tokens or 0
    totals["output_tokens"] += event.output_tokens or 0
    totals["reasoning_tokens"] += event.reasoning_tokens or 0
    totals["total_tokens"] += event.total_tokens


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


def _build_insights(summary: dict[str, int], *, window: TimeWindow) -> dict[str, object]:
    total_tokens = summary["total_tokens"]
    input_tokens = summary["input_tokens"]
    cached_input_tokens = summary["cached_input_tokens"]
    sessions = summary["sessions"]
    events = summary["events"]
    days_equivalent = _window_days(window)
    daily_equivalent_tokens = int(total_tokens / days_equivalent) if total_tokens else 0

    current_realm = _select_realm(daily_equivalent_tokens)
    current_index = REALMS.index(current_realm)
    next_realm = REALMS[current_index + 1] if current_index + 1 < len(REALMS) else None

    current_floor = current_realm["min"]
    current_ceiling = current_realm["max"]
    if current_ceiling is None:
        progress_ratio = 1.0
        tokens_to_next_realm = 0
        next_target = "最高等级"
        next_realm_name = "已达最高等级"
    else:
        segment_size = max(1, current_ceiling - current_floor)
        progress_ratio = (daily_equivalent_tokens - current_floor) / segment_size
        tokens_to_next_realm = max(0, current_ceiling - daily_equivalent_tokens)
        next_target = _format_compact(current_ceiling)
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


def _group_events(events: list[UsageEvent], key_name: str, *, limit: int) -> list[dict[str, object]]:
    grouped_totals: dict[str, dict[str, int]] = defaultdict(_blank_totals)
    grouped_sessions: dict[str, set[str]] = defaultdict(set)

    for event in events:
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

    rows: list[dict[str, object]] = []
    for name, totals in grouped_totals.items():
        row = {"name": name, **totals, "sessions": len(grouped_sessions[name])}
        rows.append(row)

    rows.sort(key=lambda item: (item["total_tokens"], item["input_tokens"]), reverse=True)
    return rows[:limit]


def build_report(
    results: list[SourceCollectResult],
    *,
    window: TimeWindow,
    group_by: str | None,
    limit: int,
) -> dict[str, object]:
    events = [event for result in results for event in result.events]
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

    summary = {
        **totals,
        "sources": len({event.source for event in events}),
        "models": len({event.model or "(unknown model)" for event in events}),
        "sessions": len(source_sessions),
        "events": len(events),
        "split_detail_events": sum(1 for event in events if _has_breakdown(event)),
        "total_only_events": sum(1 for event in events if not _has_breakdown(event)),
    }

    report = {
        "window": {
            "label": window.label,
            "timezone": window.timezone_name,
            "days_equivalent": round(_window_days(window), 2),
        },
        "summary": summary,
        "status_counts": status_counts,
        "by_source": _group_events(events, "source", limit=limit),
        "by_model": _group_events(events, "model", limit=limit),
        "by_project": _group_events(events, "project", limit=limit),
        "by_session": _group_events(events, "session", limit=limit) if group_by == "session" else [],
        "diagnostics": diagnostics[:limit],
        "benchmark_examples": BENCHMARK_EXAMPLES,
        "insights": _build_insights(summary, window=window),
        "requested_group": group_by,
    }
    return report
