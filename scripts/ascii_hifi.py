from __future__ import annotations

import textwrap
from datetime import datetime

from core.models import SourceCollectResult, TimeWindow


WIDTH = 94
INNER = WIDTH - 4
UNICODE_BAR = "█"
ASCII_BAR = "#"
UNICODE_SPARKS = "▁▂▃▄▅▆▇█"
ASCII_SPARKS = ".:-=+*#@"
UNICODE_HEAT = ("·", "░", "▒", "▓", "█")
ASCII_HEAT = (".", ".", ":", "*", "#")


def _rule(title: str) -> str:
    text = f" {title} "
    return "+" + text.ljust(WIDTH - 2, "-") + "+"


def _line(text: str = "") -> str:
    return f"| {text[:INNER].ljust(INNER)} |"


def _format_int(value: int) -> str:
    return f"{value:,}"


def _format_compact_int(value: int) -> str:
    absolute = abs(int(value))
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _format_cost(value: float) -> str:
    return f"${value:,.2f}"


def _format_compact_cost(value: float) -> str:
    absolute = abs(float(value))
    if absolute >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"${value / 1_000:.1f}k"
    return _format_cost(value)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _truncate_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = max(1, (limit - 3) // 2)
    tail = max(1, limit - 3 - head)
    return f"{text[:head]}...{text[-tail:]}"


def _wrap(text: str, limit: int) -> list[str]:
    return textwrap.wrap(
        text,
        width=limit,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def _append_field(lines: list[str], label: str, text: str) -> None:
    prefix = f"{label:<10} "
    available = INNER - len(prefix)
    wrapped = _wrap(text, available)
    for index, chunk in enumerate(wrapped):
        current_prefix = prefix if index == 0 else " " * len(prefix)
        lines.append(_line(f"{current_prefix}{chunk}"))


def _format_model_meta(node: dict[str, object] | None) -> str:
    if not node:
        return "(unknown model)"
    model = str(node.get("model") or "(unknown model)")
    raw_model = node.get("raw_model")
    resolution = str(node.get("model_resolution") or "unknown")
    source = node.get("model_source")

    details: list[str] = []
    if raw_model and str(raw_model) != model:
        details.append(f"raw {raw_model}")
    if resolution != "exact":
        details.append(resolution)
    if source and resolution != "exact":
        details.append(f"via {source}")
    if not details:
        return model
    return f"{model} ({'; '.join(details)})"


def _project_name(value: str | None) -> str:
    if not value:
        return "(unknown project)"
    normalized = str(value).rstrip("/\\")
    tail = normalized.rsplit("/", 1)[-1]
    tail = tail.rsplit("\\", 1)[-1]
    return tail or normalized


def _bar(value: int, max_value: int, *, width: int = 18, plain_ascii: bool) -> str:
    if max_value <= 0 or value <= 0:
        return "." * width if plain_ascii else "·" * width
    filled = max(1, int(round((value / max_value) * width)))
    filled = min(width, filled)
    bar_char = ASCII_BAR if plain_ascii else UNICODE_BAR
    empty_char = "." if plain_ascii else "·"
    return bar_char * filled + empty_char * (width - filled)


def _sparkline(values: list[int], *, plain_ascii: bool) -> str:
    chars = ASCII_SPARKS if plain_ascii else UNICODE_SPARKS
    if not values:
        return ""
    high = max(values)
    low = min(values)
    if high == low:
        return chars[-1] * len(values) if high > 0 else chars[0] * len(values)
    scale = len(chars) - 1
    out = []
    for value in values:
        index = int(round(((value - low) / (high - low)) * scale))
        out.append(chars[index])
    return "".join(out)


def _heat_level(value: int, thresholds: list[int]) -> int:
    level = 0
    for threshold in thresholds:
        if value >= threshold:
            level += 1
    return min(level, 4)


def _heat_thresholds(values: list[int]) -> list[int]:
    non_zero = sorted(value for value in values if value > 0)
    if not non_zero:
        return [0, 0, 0, 0]
    if len(non_zero) == 1:
        return [non_zero[0]] * 4
    indexes = [0.25, 0.5, 0.75, 0.9]
    thresholds = []
    for ratio in indexes:
        position = min(len(non_zero) - 1, int(round((len(non_zero) - 1) * ratio)))
        thresholds.append(non_zero[position])
    return thresholds


def _render_group_section(
    lines: list[str],
    title: str,
    rows: list[dict[str, object]],
    *,
    key: str,
    label: str,
    plain_ascii: bool,
) -> None:
    lines.append(_rule(title))
    if not rows:
        _append_field(lines, "说明", "当前没有可展示的数据。")
        return

    max_total = max(int(row.get("effective_tokens", row["total_tokens"])) for row in rows)
    total_sum = sum(int(row.get("effective_tokens", row["total_tokens"])) for row in rows)
    for row in rows:
        raw_name = str(row[key])
        if label == "项目":
            raw_name = _project_name(raw_name)
        name = _truncate_middle(raw_name, 28)
        total = int(row.get("effective_tokens", row["total_tokens"]))
        ratio = f"{(total / total_sum * 100):5.1f}%" if total_sum else "  0.0%"
        graph = _bar(total, max_total, plain_ascii=plain_ascii)
        _append_field(
            lines,
            label,
            f"{name:<28} {_format_compact_int(total):>8}  {ratio}  {graph}",
        )


def _render_current_session(lines: list[str], current_session: dict[str, object] | None) -> None:
    lines.append(_rule("当前会话"))
    if not current_session:
        _append_field(lines, "说明", "当前时间窗内没有会话级 usage。")
        return

    effective_tokens = int(current_session.get("effective_tokens", current_session["total_tokens"]))
    total_tokens = int(current_session["total_tokens"])
    cached_tokens = int(current_session.get("cached_input_tokens") or 0)
    _append_field(lines, "项目", _project_name(str(current_session.get("project_path") or "")))
    _append_field(lines, "模型", _format_model_meta(current_session))
    _append_field(
        lines,
        "用量",
        (
            f"去缓存后 token {_format_compact_int(effective_tokens)}   "
            f"总 token {_format_compact_int(total_tokens)}   "
            f"缓存 {_format_compact_int(cached_tokens)}"
        ),
    )


def _render_session_detail(lines: list[str], session_detail: dict[str, object] | None) -> None:
    if not session_detail:
        return
    lines.append(_rule("会话详情"))
    effective_tokens = int(session_detail.get("effective_tokens", session_detail["total_tokens"]))
    total_tokens = int(session_detail["total_tokens"])
    _append_field(lines, "项目", _project_name(str(session_detail.get("project_path") or "")))
    _append_field(lines, "模型", _format_model_meta(session_detail))
    _append_field(
        lines,
        "摘要",
        (
            f"去缓存后 token {_format_compact_int(effective_tokens)}   "
            f"总 token {_format_compact_int(total_tokens)}   "
            f"{session_detail['events']} events   "
            f"费用 {_format_compact_cost(float(session_detail.get('estimated_cost_usd', 0.0)))}"
        ),
    )


def _render_observed_only_models(lines: list[str], observed_models: list[dict[str, object]]) -> None:
    if not observed_models:
        return
    lines.append(_rule("已观测模型（未计入 token）"))
    for item in observed_models:
        sources = ", ".join(str(source) for source in item.get("sources") or [])
        _append_field(
            lines,
            "模型",
            f"{item['name']}   来源 {sources or '(unknown)'}   仅观测到使用痕迹，当前无 exact token payload",
        )


def _render_observed_only_sources(lines: list[str], observed_sources: list[dict[str, object]]) -> None:
    if not observed_sources:
        return
    lines.append(_rule("已观测来源（未计入 token）"))
    for item in observed_sources:
        _append_field(
            lines,
            "来源",
            f"{item['source_id']}   {item['display_name']}   已识别到本机痕迹/缓存，当前无 exact token payload",
        )


def _render_trend(lines: list[str], trend: dict[str, object], *, plain_ascii: bool) -> None:
    lines.append(_rule(f"最近 {trend['days']} 天（去缓存后）"))
    points = trend["points"]
    if not points:
        _append_field(lines, "说明", "当前时间窗内没有每日数据。")
        return

    values = [int(item.get("effective_tokens", item["total_tokens"])) for item in points]
    max_total = max(values) if values else 0
    stats = [
        f"合计 {_format_compact_int(int(trend['total_tokens']))}  估算 {_format_compact_cost(float(trend.get('estimated_cost_usd', 0.0)))}",
        f"均值 {_format_compact_int(int(trend['avg_tokens']))}",
        f"最高 {_format_compact_int(int(trend['max_tokens']))}",
    ]
    trend_width = 42
    for row_index, item in enumerate(points):
        date_label = str(item["date"])[5:]
        total = int(item.get("effective_tokens", item["total_tokens"]))
        graph = _bar(total, max_total, width=24, plain_ascii=plain_ascii)
        left = f"{graph}  {_format_compact_int(total)}"
        right = stats[row_index] if row_index < len(stats) else ""
        _append_field(
            lines,
            date_label,
            f"{left:<{trend_width}} {right}".rstrip(),
        )


def _render_calendar(lines: list[str], calendar: dict[str, object], *, plain_ascii: bool) -> None:
    lines.append(_rule(f"本月分布 {calendar['month']}（去缓存后）"))

    days = calendar["days"]
    if not days:
        _append_field(lines, "说明", "当前月份没有 usage 数据。")
        return

    thresholds = _heat_thresholds([int(item.get("effective_tokens", item["total_tokens"])) for item in days])
    chars = ASCII_HEAT if plain_ascii else UNICODE_HEAT
    lines.append(_line("Mo    Tu    We    Th    Fr    Sa    Su"))

    first = datetime.fromisoformat(f"{days[0]['date']}T00:00:00")
    prefix = []
    weekday = first.weekday()
    for _ in range(weekday):
        prefix.append("     ")

    cells = prefix[:]
    for item in days:
        level = _heat_level(int(item.get("effective_tokens", item["total_tokens"])), thresholds)
        day_label = datetime.fromisoformat(f"{item['date']}T00:00:00").strftime("%d")
        cells.append(f"{day_label}{chars[level]}  ")

    stats = [
        f"合计 {_format_compact_int(int(calendar.get('effective_tokens', calendar.get('total_tokens', 0))))}  估算 {_format_compact_cost(float(calendar.get('estimated_cost_usd', 0.0)))}",
        f"均值 {_format_compact_int(int(calendar.get('avg_tokens', 0)))}",
        f"最高 {_format_compact_int(int(calendar.get('max_tokens', 0)))}",
    ]
    calendar_width = 40
    for index in range(0, len(cells), 7):
        row_index = index // 7
        left = "".join(cells[index:index + 7]).rstrip()
        right = stats[row_index] if row_index < len(stats) else ""
        if right:
            lines.append(_line(f"{left:<{calendar_width}} {right}"))
        else:
            lines.append(_line(left))


def _render_diagnostics(
    lines: list[str],
    diagnostics: list[dict[str, object]] | None,
    *,
    show_when_empty: bool,
) -> None:
    if not diagnostics and not show_when_empty:
        return

    lines.append(_rule("诊断 / 缺失来源"))
    if not diagnostics:
        _append_field(lines, "说明", "当前未发现缺失来源或校验问题。")
        return

    for item in diagnostics[:5]:
        source = str(item.get("source") or "unknown")
        label = "费用" if source == "estimated-cost" else source
        _append_field(lines, label, str(item.get("reason") or ""))


def render_report(report: dict[str, object], *, plain_ascii: bool = False, show_estimated_cost: bool = False) -> str:
    summary = report["summary"]
    lines = [
        _rule("Token 用量"),
        _rule("总览"),
    ]

    _append_field(lines, "时间", str(report["window"]["label"]))
    _append_field(lines, "总 token", _format_compact_int(int(summary["total_tokens"])))
    _append_field(lines, "去缓存后", f"token {_format_compact_int(int(summary.get('effective_tokens', summary['total_tokens'])))}")
    if summary["total_tokens"] and summary["split_detail_events"] == 0:
        _append_field(lines, "构成", "当前来源只提供 total_tokens，暂时无法精确拆出缓存前后。")
    else:
        input_line = (
            f"{_format_compact_int(int(summary['input_tokens']))}   "
            f"缓存 {_format_compact_int(int(summary['cached_input_tokens']))}   "
            f"输出 {_format_compact_int(int(summary['output_tokens']))}   "
            f"推理 {_format_compact_int(int(summary['reasoning_tokens']))}"
        )
        if summary["total_only_events"]:
            input_line += f"   另有 {summary['total_only_events']} 个事件仅含 total_tokens"
        _append_field(lines, "构成", f"输入 {input_line}")
    if show_estimated_cost or float(summary.get("estimated_cost_usd", 0.0)):
        _append_field(
            lines,
            "费用",
            f"估算 {_format_cost(float(summary.get('estimated_cost_usd', 0.0)))}",
        )
    if int(summary.get("observed_only_sources", 0)) or int(summary.get("observed_only_models", 0)):
        _append_field(
            lines,
            "观测层",
            (
                f"未计量来源 {int(summary.get('observed_only_sources', 0))}   "
                f"未计量模型 {int(summary.get('observed_only_models', 0))}   "
                "下方会单列展示，避免静默漏掉"
            ),
        )

    _render_current_session(lines, report.get("current_session"))

    dashboard_mode = report.get("dashboard_mode")
    show_dashboard_groups = dashboard_mode in {"today", "recent"}
    if report.get("requested_group") == "source" or len(report["by_source"]) > 1:
        _render_group_section(lines, "按来源（去缓存后）", report["by_source"], key="name", label="来源", plain_ascii=plain_ascii)
    _render_observed_only_sources(lines, report.get("observed_only_sources") or [])
    if report.get("requested_group") == "model" or show_dashboard_groups or len(report["by_model"]) > 1:
        _render_group_section(lines, "按模型（去缓存后）", report["by_model"], key="name", label="模型", plain_ascii=plain_ascii)
    if report.get("requested_group") == "project" or show_dashboard_groups or len(report["by_project"]) > 1:
        _render_group_section(lines, "按项目（去缓存后）", report["by_project"], key="name", label="项目", plain_ascii=plain_ascii)
    _render_observed_only_models(lines, report.get("observed_only_models") or [])

    if report.get("requested_group") == "session":
        _render_group_section(lines, "按会话（去缓存后）", report["by_session"], key="name", label="会话", plain_ascii=plain_ascii)
    if report.get("requested_group") == "day":
        day_rows = [
            {
                "name": item["date"],
                **item,
            }
            for item in report["by_day"][-5:]
        ]
        _render_group_section(lines, "按天（去缓存后）", day_rows, key="name", label="日期", plain_ascii=plain_ascii)

    requested_trend = report.get("requested_trend")
    if requested_trend == "7d":
        _render_trend(lines, report["charts"]["trend_7d"], plain_ascii=plain_ascii)
    elif requested_trend == "30d":
        _render_trend(lines, report["charts"]["trend_30d"], plain_ascii=plain_ascii)
    elif dashboard_mode == "today":
        _render_trend(lines, report["charts"]["trend_7d"], plain_ascii=plain_ascii)
    elif dashboard_mode == "recent":
        _render_trend(lines, report["charts"]["trend_30d"], plain_ascii=plain_ascii)

    if report.get("requested_calendar") == "month":
        _render_calendar(lines, report["charts"]["calendar_month"], plain_ascii=plain_ascii)
    elif dashboard_mode in {"today", "recent"}:
        _render_calendar(lines, report["charts"]["calendar_month"], plain_ascii=plain_ascii)

    _render_session_detail(lines, report.get("session_detail"))

    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)


def render_sources(results: list[SourceCollectResult]) -> str:
    lines = [
        _rule("Token Usage 来源状态"),
        _line("来源                      状态                精度         摘要"),
    ]
    for result in results:
        detection = result.detection
        lines.append(
            _line(
                f"{detection.source_id:24}  "
                f"{detection.status:18}  "
                f"{detection.accuracy_level:10}  "
                f"{_truncate_middle(detection.summary, 26)}"
            )
        )
        for path in detection.candidate_paths[:2]:
            lines.append(_line(f"路径      {_truncate_middle(path, INNER - 10)}"))
    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)


def render_diagnose(result: SourceCollectResult, window: TimeWindow) -> str:
    detection = result.detection
    lines = [
        _rule(f"诊断 {detection.source_id}"),
    ]
    _append_field(lines, "时间窗口", str(window.label))
    _append_field(lines, "状态", f"{detection.status} / {detection.accuracy_level}")
    _append_field(lines, "摘要", detection.summary)
    _append_field(lines, "文件数", str(result.scanned_files))
    _append_field(lines, "事件数", str(len(result.events)))
    if detection.candidate_paths:
        lines.append(_rule("候选路径"))
        for path in detection.candidate_paths[:5]:
            _append_field(lines, "路径", _truncate_middle(path, INNER - 10))
    if detection.details:
        lines.append(_rule("识别"))
        for detail in detection.details[:5]:
            _append_field(lines, "说明", _truncate_middle(detail, INNER - 10))
    if result.verification_issues:
        lines.append(_rule("校验"))
        for issue in result.verification_issues[:5]:
            _append_field(lines, "问题", _truncate_middle(issue, INNER - 10))
    if result.skipped_reasons:
        lines.append(_rule("跳过原因"))
        for issue in result.skipped_reasons[:5]:
            _append_field(lines, "原因", _truncate_middle(issue, INNER - 10))
    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)


def render_health(health: dict[str, object]) -> str:
    lines = [
        _rule("Token Usage Universal · Health"),
        _rule("总览"),
    ]
    _append_field(lines, "状态", str(health["overall_status"]))
    _append_field(lines, "摘要", str(health["summary"]))
    _append_field(
        lines,
        "可用来源",
        f"{health['ready_sources']} / {health['supported_sources']}",
    )

    lines.append(_rule("环境变量"))
    for item in health["environment_variables"]:
        status = "configured" if item["configured"] else "default"
        value = item["value"] or item["default"] or "(empty)"
        _append_field(lines, item["name"], f"{status}   {_truncate_middle(str(value), 54)}")

    lines.append(_rule("来源"))
    for item in health["sources"]:
        _append_field(
            lines,
            item["source_id"],
            f"{item['status']} / {item['accuracy_level']}   {item['summary']}",
        )

    lines.append(_rule("下一步"))
    for step in health["next_steps"]:
        _append_field(lines, "建议", step)

    lines.append(_rule("命令"))
    for command in health["recommended_commands"]:
        _append_field(lines, "运行", command)

    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)


def render_targets(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    scope = payload["scope"]
    ecosystems = payload["ecosystems"]

    lines = [
        _rule("Top20 Ecosystem Registry"),
        _rule("范围"),
    ]
    _append_field(lines, "冻结口径", str(scope["frozen_by"]))
    _append_field(lines, "Surface", ", ".join(scope["surfaces"]))
    _append_field(lines, "采集层", ", ".join(scope["capture_lanes"]))

    lines.append(_rule("摘要"))
    _append_field(lines, "生态数", str(summary["total_ecosystems"]))
    _append_field(
        lines,
        "优先级",
        f"中国优先 {summary['china_priority_ecosystems']}   全球补齐 {summary['global_ecosystems']}",
    )
    _append_field(lines, "Surface 数", str(summary["total_surfaces"]))
    provider_text = "   ".join(f"{key} {value}" for key, value in summary["provider_lane_maturity"].items())
    _append_field(lines, "Provider", provider_text)
    surface_text = "   ".join(f"{key} {value}" for key, value in summary["surface_maturity"].items())
    _append_field(lines, "Surface", surface_text)

    lines.append(_rule("生态"))
    for ecosystem in ecosystems:
        _append_field(
            lines,
            ecosystem["ecosystem_id"],
            f"{ecosystem['display_name']}   {ecosystem['priority_group']}   provider {ecosystem['provider_lane_maturity']}",
        )
        provider_ids = ecosystem.get("provider_source_ids") or []
        if provider_ids:
            _append_field(lines, "provider", ", ".join(str(item) for item in provider_ids))
        for surface in ecosystem["surfaces"]:
            source_bits = list(surface.get("implemented_source_ids") or [])
            source_bits.extend(surface.get("planned_source_ids") or [])
            suffix = f"   sources {', '.join(source_bits)}" if source_bits else ""
            _append_field(
                lines,
                surface["surface_type"],
                f"{surface['display_name']}   {surface['primary_lane']}   {surface['maturity']}{suffix}",
            )
    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)


def render_release_gate(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    metrics = payload["metrics"]
    platform_matrix = payload["platform_matrix"]
    source_state_summary = payload.get("source_state_summary") or {}
    baseline = payload.get("baseline") or {}
    baseline_diff = baseline.get("diff") or {}

    lines = [
        _rule("Release Gate"),
        _rule("摘要"),
    ]
    _append_field(lines, "状态", f"{summary['status']}   {summary['passed_gates']}/{summary['total_gates']} gates passed")
    _append_field(lines, "证据范围", str(summary["evidence_scope"]))
    _append_field(lines, "覆盖率", _percent(float(metrics["coverage_ratio"])))
    _append_field(lines, "中国优先", _percent(float(metrics["china_priority_ratio"])))
    _append_field(lines, "exact 覆盖", _percent(float(metrics["exact_surface_ratio"])))
    _append_field(lines, "默认去重", _percent(float(metrics["default_duplicate_event_ratio"])))
    _append_field(lines, "Explain", _percent(float(metrics["diagnose_explainability_ratio"])))
    _append_field(
        lines,
        "来源状态",
        (
            f"exact {int(source_state_summary.get('exact', 0))}   "
            f"diagnose {int(source_state_summary.get('diagnose', 0))}   "
            f"unsupported {int(source_state_summary.get('unsupported', 0))}"
        ),
    )

    lines.append(_rule("门禁"))
    for gate in payload["gates"]:
        _append_field(
            lines,
            gate["gate_id"],
            f"{gate['status']}   {gate['label']}   actual {gate['actual']}   threshold {gate['threshold']}",
        )

    gap_section_opened = False
    if payload.get("missing_backing_source_ids"):
        lines.append(_rule("缺口"))
        gap_section_opened = True
        _append_field(lines, "missing", ", ".join(payload["missing_backing_source_ids"]))

    duplicate_probe = payload.get("duplicate_probe") or {}
    manual_only_source_ids = duplicate_probe.get("manual_only_source_ids") or []
    if manual_only_source_ids:
        if not gap_section_opened:
            lines.append(_rule("缺口"))
            gap_section_opened = True
        _append_field(lines, "manual", ", ".join(manual_only_source_ids))

    lines.append(_rule("平台"))
    _append_field(
        lines,
        "macOS",
        (
            f"{platform_matrix['macos']['supported']}   "
            f"{platform_matrix['macos']['covered_sources']}/{platform_matrix['macos']['total_sources']}   "
            f"{platform_matrix['macos']['evidence_scope']}"
        ),
    )
    _append_field(
        lines,
        "Windows",
        (
            f"{platform_matrix['windows']['supported']}   "
            f"{platform_matrix['windows']['covered_sources']}/{platform_matrix['windows']['total_sources']}   "
            f"{platform_matrix['windows']['evidence_scope']}"
        ),
    )
    _append_field(
        lines,
        "Linux",
        (
            f"{platform_matrix['linux']['supported']}   "
            f"{platform_matrix['linux']['covered_sources']}/{platform_matrix['linux']['total_sources']}   "
            f"{platform_matrix['linux']['evidence_scope']}"
        ),
    )

    if baseline_diff:
        lines.append(_rule("Baseline"))
        _append_field(lines, "路径", str(baseline.get("path") or "(unknown)"))
        _append_field(
            lines,
            "变化",
            (
                f"regressed {baseline_diff['counts']['regressed']}   "
                f"improved {baseline_diff['counts']['improved']}   "
                f"new {baseline_diff['counts']['new_sources']}   "
                f"removed {baseline_diff['counts']['removed_sources']}"
            ),
        )
        if baseline_diff.get("regressed"):
            _append_field(lines, "退化", ", ".join(str(item) for item in baseline_diff["regressed"]))
        if baseline_diff.get("improved"):
            _append_field(lines, "提升", ", ".join(str(item) for item in baseline_diff["improved"]))

    lines.append(_rule("备注"))
    for note in payload.get("notes", []):
        _append_field(lines, "note", note)

    lines.append("+" + "-" * (WIDTH - 2) + "+")
    return "\n".join(lines)
