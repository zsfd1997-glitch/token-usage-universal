from __future__ import annotations

import textwrap

from core.models import SourceCollectResult, TimeWindow


WIDTH = 94
INNER = WIDTH - 4


def _rule(title: str) -> str:
    text = f" {title} "
    return "+" + text.ljust(WIDTH - 2, "-") + "+"


def _line(text: str = "") -> str:
    return f"| {text[:INNER].ljust(INNER)} |"


def _format_int(value: int) -> str:
    return f"{value:,}"


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


def render_report(report: dict[str, object]) -> str:
    summary = report["summary"]
    status_counts = report["status_counts"]
    insights = report["insights"]
    lines = [
        _rule("Token Usage Universal · 修行面板"),
        _rule("总览"),
    ]

    _append_field(lines, "时间窗口", str(report["window"]["label"]))
    _append_field(lines, "统计范围", "all exact sources")
    _append_field(
        lines,
        "状态",
        (
            f"exact={status_counts['exact']}  "
            f"derived={status_counts['derived']}  "
            f"estimated={status_counts['estimated']}  "
            f"unsupported={status_counts['unsupported']}"
        ),
    )
    _append_field(lines, "总量", _format_int(summary["total_tokens"]))
    if summary["total_tokens"] and summary["split_detail_events"] == 0:
        _append_field(lines, "输入", "当前来源只提供 total_tokens，未提供输入 / 缓存 / 输出拆分。")
    else:
        input_line = (
            f"{_format_int(summary['input_tokens'])}   "
            f"缓存 {_format_int(summary['cached_input_tokens'])}   "
            f"输出 {_format_int(summary['output_tokens'])}"
        )
        if summary["total_only_events"]:
            input_line += f"   另有 {summary['total_only_events']} 个事件仅含 total_tokens"
        _append_field(lines, "输入", input_line)
    _append_field(
        lines,
        "推理",
        (
            f"{_format_int(summary['reasoning_tokens'])}   "
            f"来源 {summary['sources']}   "
            f"模型 {summary['models']}   "
            f"会话 {summary['sessions']}   "
            f"事件 {summary['events']}"
        ),
    )
    _append_field(lines, "折算天数", f"{report['window']['days_equivalent']} day")

    lines.append(_rule("等级评定"))
    _append_field(
        lines,
        "模型口径",
        (
            f"{insights['model_anchor_openai']}；"
            f"{insights['model_anchor_anthropic']}（核验日期：{insights['model_anchor_verified_at']}）"
        ),
    )
    _append_field(
        lines,
        "等级",
        f"{insights['realm_name']}（{insights['realm_label']}，{insights['realm_band']}）",
    )
    _append_field(lines, "岗位对标", str(insights["role_anchor"]))
    _append_field(lines, "团队场景", str(insights["team_anchor"]))
    _append_field(lines, "模型锚点", str(insights["model_reference"]))
    _append_field(lines, "日等效", f"{insights['compact_daily_equivalent']} / day")
    if insights["tokens_to_next_realm"]:
        _append_field(
            lines,
            "升级进度",
            (
                f"{insights['meter']}  当前 {insights['compact_daily_equivalent']}/day，"
                f"距离 {insights['next_realm_name']} 还差 {insights['compact_to_next_realm']}/day"
            ),
        )
    else:
        _append_field(lines, "升级进度", f"{insights['meter']}  已达当前最高等级")
    _append_field(
        lines,
        "参考说明",
        f"{insights['business_comment']} {insights['reference_note']}",
    )
    _append_field(lines, "建议", str(insights["business_suggestion"]))
    _append_field(
        lines,
        "修行数据",
        (
            f"avg/session {_format_int(insights['avg_per_session'])}   "
            f"avg/event {_format_int(insights['avg_per_event'])}   "
            f"cache ratio {insights['cache_ratio'] * 100:.2f}%"
        ),
    )

    lines.append(_rule("按来源"))
    if report["by_source"]:
        for row in report["by_source"]:
            _append_field(
                lines,
                _truncate_middle(str(row["name"]), 10),
                f"{_format_int(row['total_tokens'])}   {str(row['sessions']).rjust(3)} sessions",
            )
    else:
        _append_field(lines, "说明", "所选时间窗内未发现 exact usage 事件。")

    lines.append(_rule("按模型"))
    if report["by_model"]:
        for row in report["by_model"]:
            _append_field(
                lines,
                "模型",
                f"{_truncate_middle(str(row['name']), 52)}   {_format_int(row['total_tokens'])}",
            )
    else:
        _append_field(lines, "说明", "当前没有可展示的模型级 usage。")

    lines.append(_rule("按项目"))
    if report["by_project"]:
        for row in report["by_project"]:
            _append_field(
                lines,
                "项目",
                f"{_truncate_middle(str(row['name']), 52)}   {_format_int(row['total_tokens'])}",
            )
    else:
        _append_field(lines, "说明", "当前没有可展示的项目级 usage。")

    if report["requested_group"] == "session":
        lines.append(_rule("按会话"))
        for row in report["by_session"]:
            _append_field(
                lines,
                "会话",
                f"{_truncate_middle(str(row['name']), 52)}   {_format_int(row['total_tokens'])}",
            )

    lines.append(_rule("诊断"))
    diagnostics = report["diagnostics"]
    if diagnostics:
        for item in diagnostics:
            _append_field(lines, item["source"], str(item["reason"]))
    else:
        _append_field(lines, "说明", "没有额外诊断警告。")

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
