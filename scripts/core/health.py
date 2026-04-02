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
        steps.append(
            "Claude 要拿 exact，需要 local-agent-mode-sessions 下存在带 total_tokens + executor_end/grader_end 的 JSON"
            "（旧版常见 timing.json）；mac 默认在 ~/Library/Application Support/Claude/local-agent-mode-sessions，"
            "Windows 默认在 %APPDATA%\\Claude\\local-agent-mode-sessions，路径不同就设 TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT。"
        )

    opencode = by_source.get("opencode")
    if opencode and not opencode.available:
        steps.append(
            "OpenCode 优先走官方 CLI export；如 CLI 不在 PATH，请设置 TOKEN_USAGE_OPENCODE_BIN；"
            "如果本地数据目录不在默认位置，请设置 TOKEN_USAGE_OPENCODE_ROOTS。"
        )

    minimax = by_source.get("minimax-agent")
    if minimax and not minimax.available:
        steps.append(
            "MiniMax Agent 目前走桌面端 Chromium Cache_Data exact 解析；"
            "mac 默认在 ~/Library/Application Support/MiniMax Agent，Windows 常见在 %APPDATA%\\MiniMax Agent，"
            "路径不同就设 TOKEN_USAGE_MINIMAX_AGENT_ROOT。"
        )

    generic = by_source.get("generic-openai-compatible")
    if generic and not generic.available:
        steps.append(
            "如要接入通用 API exact 日志，优先确认常见目录是否已自动发现；"
            "若日志不在标准位置，请设置 TOKEN_USAGE_GENERIC_LOG_GLOBS 或 TOKEN_USAGE_DISCOVERY_ROOTS。"
        )

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
            "python3 scripts/token_usage.py health",
            "python3 scripts/token_usage.py sources",
            "python3 scripts/token_usage.py report --today",
        ],
        "next_steps": _next_steps(detections),
    }
