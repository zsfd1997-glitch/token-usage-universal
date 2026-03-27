from __future__ import annotations

from core.config import environment_variable_statuses
from core.models import SourceCollectResult, SourceDetection


def _next_steps(detections: list[SourceDetection]) -> list[str]:
    steps: list[str] = []
    by_source = {item.source_id: item for item in detections}

    codex = by_source.get("codex")
    if codex and not codex.available:
        steps.append("如 Codex 日志不在默认位置，请设置 TOKEN_USAGE_CODEX_ROOT 后重试 health。")

    claude = by_source.get("claude-code")
    if claude and not claude.available:
        steps.append("Claude 只有 transcript 不够；要拿 exact total，需要 local-agent-mode-sessions 下的 timing.json。")

    generic = by_source.get("generic-openai-compatible")
    if generic and not generic.available:
        steps.append("如要接入通用 OpenAI-compatible 日志，请设置 TOKEN_USAGE_GENERIC_LOG_GLOBS。")

    steps.append("先运行 sources 看来源状态，再运行 report --today 拿今日主结论。")
    return steps


def build_health_report(results: list[SourceCollectResult]) -> dict[str, object]:
    detections = [item.detection for item in results]
    ready = [item for item in detections if item.available]
    supported = [item for item in detections if item.supported]

    if len(ready) == len(supported) and supported:
        overall_status = "ready"
        summary = "所有已支持来源都已具备可用真源。"
    elif ready:
        overall_status = "partial"
        summary = "至少有一个来源已可用，但仍有来源需要配置或补真源。"
    else:
        overall_status = "needs-configuration"
        summary = "当前还没有可直接统计的来源，请先完成路径配置或补齐真源。"

    return {
        "overall_status": overall_status,
        "summary": summary,
        "ready_sources": len(ready),
        "supported_sources": len(supported),
        "sources": [item.as_dict() for item in detections],
        "environment_variables": environment_variable_statuses(),
        "recommended_commands": [
            'python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health',
            'python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" sources',
            'python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today',
        ],
        "next_steps": _next_steps(detections),
    }
