#!/usr/bin/env python3
"""Standalone CLI runtime for token-usage-universal."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _configure_stdio_utf8() -> None:
    # Intranet GBK terminals (Windows cmd cp936, zh_CN.GBK locale) cannot
    # encode every unicode char; without intervention print() raises
    # UnicodeEncodeError and crashes mid-panel. Guarantees:
    #   1. If PYTHONIOENCODING is set, keep that codec — the user (or CI)
    #      made an explicit choice — but force errors="backslashreplace" so
    #      any unencodable char degrades to an escape instead of crashing.
    #      Escaped output stays valid JSON (\uXXXX) and parseable ASCII.
    #   2. Otherwise prefer UTF-8 with the same non-crashing error handler.
    user_set = bool(os.environ.get("PYTHONIOENCODING"))
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        if user_set:
            try:
                reconfigure(errors="backslashreplace")
            except (LookupError, ValueError):
                continue
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
            continue
        except (LookupError, ValueError):
            pass
        try:
            reconfigure(errors="backslashreplace")
        except (LookupError, ValueError):
            continue


_configure_stdio_utf8()


def _stdout_needs_ascii_json() -> bool:
    # When stdout is not UTF-8 (cp1252 CI, GBK intranet terminals, unknown
    # pipes), raw non-ASCII chars in JSON become codec-specific bytes that
    # downstream UTF-8 consumers (test harnesses, skills reading the pipe)
    # can't decode. Falling back to ensure_ascii=True keeps stdout pure ASCII
    # (\uXXXX escapes are valid JSON) so the bytes round-trip through any
    # codec without loss or decode errors.
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return not encoding.startswith("utf")


_STDOUT_JSON_ENSURE_ASCII = _stdout_needs_ascii_json()

from adapters.claude_code import ClaudeCodeAdapter
from adapters.claude_desktop import ClaudeDesktopAdapter
from adapters.chromium_desktop_family import build_chromium_desktop_family_adapters
from adapters.compatible_api_family import build_provider_api_adapters
from adapters.codex import CodexAdapter
from adapters.gemini_cli import GeminiCliAdapter
from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from adapters.kimi_cli import KimiCliAdapter
from adapters.minimax_agent import MiniMaxAgentAdapter
from adapters.opencode import OpenCodeAdapter
from adapters.trae import TraeAdapter
from adapters.qwen_code_cli import QwenCodeCliAdapter
from ascii_hifi import render_diagnose, render_health, render_release_gate, render_report, render_sources, render_targets
from core.health import build_health_report
from core.ingress_companion import (
    build_ingress_companion_config,
    build_ingress_companion_payload,
    render_ingress_companion_payload,
    serve_ingress_companion,
)
from core.ingress_bootstrap import (
    build_ingress_bootstrap_payload,
    build_ingress_profiles_payload,
    payload_to_json,
    render_ingress_bootstrap_payload,
    render_ingress_profiles_payload,
)
from core.aggregator import build_report
from core.ecosystem_registry import build_top20_registry_payload
from core.models import SourceCollectResult
from core.release_gate import build_release_gate_payload, classify_source_state, diff_against_baseline
from core.time_window import build_month_window, build_time_window, within_window
from core.verifier import verify_result


def _build_adapters():
    adapters = [
        CodexAdapter(),
        ClaudeCodeAdapter(),
        ClaudeDesktopAdapter(),
        OpenCodeAdapter(),
        TraeAdapter(),
        MiniMaxAgentAdapter(),
        QwenCodeCliAdapter(),
        KimiCliAdapter(),
        GeminiCliAdapter(),
        *build_chromium_desktop_family_adapters(),
        *build_provider_api_adapters(),
        GenericOpenAICompatibleAdapter(),
    ]
    return {adapter.source_id: adapter for adapter in adapters}


def _resolve_sources(args, registry):
    requested = args.source or []
    if not requested:
        return [adapter for adapter in registry.values() if getattr(adapter, "default_selected", True)]

    selected = []
    for source_id in requested:
        adapter = registry.get(source_id)
        if not adapter:
            raise SystemExit(f"unknown source: {source_id}")
        selected.append(adapter)
    return selected


def _collect_results(window, adapters, *, chart_mode: bool = False):
    results = []
    for adapter in adapters:
        result = adapter.collect_chart(window) if chart_mode else adapter.collect(window)
        result.verification_issues.extend(verify_result(result))
        results.append(result)
    return results


def _window_within(inner, outer) -> bool:
    if inner.start and outer.start and inner.start < outer.start:
        return False
    if inner.end and outer.end and inner.end > outer.end:
        return False
    return True


def _filter_results_to_window(window, results):
    filtered = []
    for result in results:
        filtered.append(
            SourceCollectResult(
                detection=result.detection,
                events=[event for event in result.events if within_window(window, event.timestamp)],
                scanned_files=result.scanned_files,
                verification_issues=list(result.verification_issues),
                skipped_reasons=list(result.skipped_reasons),
            )
        )
    return filtered


def _time_window_from_args(args):
    if getattr(args, "calendar", None) == "month" and not any(
        (getattr(args, "today", False), getattr(args, "last", None), getattr(args, "start", None), getattr(args, "end", None))
    ):
        return build_month_window(getattr(args, "month", None), getattr(args, "tz", None))

    if getattr(args, "trend", None) and not any(
        (getattr(args, "today", False), getattr(args, "last", None), getattr(args, "start", None), getattr(args, "end", None))
    ):
        return build_time_window(
            today=False,
            last=getattr(args, "trend"),
            start=None,
            end=None,
            tz_name=getattr(args, "tz", None),
        )

    return build_time_window(
        today=getattr(args, "today", False),
        last=getattr(args, "last", None),
        start=getattr(args, "start", None),
        end=getattr(args, "end", None),
        tz_name=getattr(args, "tz", None),
    )


def _json_default(value):
    if hasattr(value, "as_dict"):
        return value.as_dict()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _source_status_payload(adapter) -> dict[str, object]:
    result = SourceCollectResult(detection=adapter.detect())
    payload = result.as_dict()
    detection = payload["detection"]
    payload.update(
        {
            "source_id": detection["source_id"],
            "display_name": detection["display_name"],
            "provider": detection["provider"],
            "accuracy_level": detection["accuracy_level"],
            "supported": detection["supported"],
            "available": detection["available"],
            "status": detection["status"],
            "in_default_rollup": getattr(adapter, "default_selected", True),
        }
    )
    detection["in_default_rollup"] = payload["in_default_rollup"]
    return payload


def _source_status_payload_from_result(result: SourceCollectResult, *, in_default_rollup: bool) -> dict[str, object]:
    payload = result.as_dict()
    detection = payload["detection"]
    payload.update(
        {
            "source_id": detection["source_id"],
            "display_name": detection["display_name"],
            "provider": detection["provider"],
            "accuracy_level": detection["accuracy_level"],
            "supported": detection["supported"],
            "available": detection["available"],
            "status": detection["status"],
            "in_default_rollup": in_default_rollup,
            "state": classify_source_state(detection),
        }
    )
    detection["in_default_rollup"] = payload["in_default_rollup"]
    detection["state"] = payload["state"]
    return payload


def _load_release_gate_baseline(path: Path) -> dict[str, object]:
    baseline_path = path.expanduser()
    release_gate_file = baseline_path / "release_gate.json"
    sources_file = baseline_path / "sources.json"

    if release_gate_file.is_file():
        payload = json.loads(release_gate_file.read_text(encoding="utf-8"))
        if payload.get("source_states"):
            return payload

    if sources_file.is_file():
        sources_payload = json.loads(sources_file.read_text(encoding="utf-8"))
        return {"sources": sources_payload}

    raise SystemExit(
        f"baseline bundle must contain release_gate.json with source_states or sources.json: {baseline_path}"
    )


def _dashboard_mode_from_args(args) -> str | None:
    if args.dashboard and args.dashboard != "auto":
        return args.dashboard

    if any((args.by, args.trend, args.calendar, args.session, args.current_session)):
        return None

    has_explicit_window = any((args.today, args.last, args.start, args.end))
    if args.dashboard == "auto":
        if args.last or args.start or args.end:
            return "recent"
        return "today"
    if args.last or args.start or args.end:
        return "recent"
    if not has_explicit_window or args.today:
        return "today"
    return None


def _should_preaggregate_results(args, window) -> bool:
    if args.format == "json" or args.session:
        return False
    if not window.start or not window.end:
        return False
    return (window.end - window.start).total_seconds() >= 86400


def command_report(args) -> int:
    registry = _build_adapters()
    window = _time_window_from_args(args)
    selected_adapters = _resolve_sources(args, registry)
    dashboard_mode = _dashboard_mode_from_args(args)
    preaggregated_results = _collect_results(window, selected_adapters, chart_mode=True) if _should_preaggregate_results(args, window) else None
    chart_results = None
    if dashboard_mode in {"today", "recent"} and not args.trend and not args.calendar:
        if dashboard_mode == "recent" and args.last == "30d" and not args.start and not args.end and preaggregated_results is not None:
            results = preaggregated_results
            chart_results = preaggregated_results
        else:
            chart_window = build_time_window(
                today=False,
                last="30d",
                start=None,
                end=None,
                tz_name=getattr(args, "tz", None),
            )
            if _window_within(window, chart_window):
                chart_results = _collect_results(chart_window, selected_adapters, chart_mode=True)
                results = preaggregated_results if preaggregated_results is not None else _filter_results_to_window(window, chart_results)
            else:
                results = preaggregated_results if preaggregated_results is not None else _collect_results(window, selected_adapters)
                chart_results = _collect_results(chart_window, selected_adapters, chart_mode=True)
    else:
        results = preaggregated_results if preaggregated_results is not None else _collect_results(window, selected_adapters)

    report = build_report(
        results,
        window=window,
        group_by=args.by,
        limit=args.limit,
        trend=args.trend,
        calendar=args.calendar,
        calendar_month=args.month,
        session_id=args.session,
        chart_results=chart_results,
        dashboard_mode=dashboard_mode,
    )
    if args.format == "json":
        print(json.dumps({"results": [item.as_dict() for item in results], "report": report}, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_report(report, plain_ascii=args.plain_ascii, show_estimated_cost=(args.estimated_cost or bool(dashboard_mode))))
    return 0


def command_sources(args) -> int:
    registry = _build_adapters()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    if args.format == "json":
        print(json.dumps([_source_status_payload(adapter) for adapter in registry.values()], ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_sources(results))
    return 0


def command_health(args) -> int:
    registry = _build_adapters()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    health = build_health_report(results)
    if args.format == "json":
        print(json.dumps(health, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_health(health))
    return 0


def command_diagnose(args) -> int:
    registry = _build_adapters()
    adapter = registry.get(args.source)
    if not adapter:
        raise SystemExit(f"unknown source: {args.source}")
    window = _time_window_from_args(args)
    result = adapter.collect(window)
    result.verification_issues.extend(verify_result(result))
    if args.format == "json":
        print(json.dumps(result.as_dict(), ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_diagnose(result, window))
    return 0


_BOOTSTRAP_PROMPT_TEMPLATE = """你现在要扮演 token-usage-universal 这个本地工具的翻译层。
工具入口：python3 {cli_path}
规则：
- 触发词：token / 用量 / 消耗量 / 使用量 / 消耗。用户说这五个词之一，默认跑 `report --today`。
- 按模型/项目/来源拆：加 `--by model|project|source`。
- 趋势：`report --trend 7d` 或 `--trend 30d`。
- 当前会话：`report --current-session`。
- 排障：`diagnose --source <source_id> --today`。
- 来源状态：`sources` 或 `health`。
输出协议：
- CLI 返回的 ascii-hifi 面板必须原样放进 fenced code block，再补 1-3 句高信号结论，末句给可选展开方向。
- 结果为 0 必须解释"为什么是 0"，不允许空白成功。
- 总 token 和去缓存后 token 要分开说，不允许只给裸数字。
终端编码：
- 如果中文渲染成乱码或 `chcp` 返回 936，先让用户 `chcp 65001`（Windows）或 `export LANG=en_US.UTF-8`，或设 `PYTHONIOENCODING=gbk:backslashreplace`；实在不行改跑 `--format json` 再由我自己重绘英文面板。
禁忌：
- 不拆桌面/CLI/插件为多条 source；它们共享同一条 `opencode` source。
- 不在默认路径 not_found 时直接断言"没用量"；先路径探测。
- 不中英混排输出到 GBK 终端。
用户停手（"先这样/够了/不用继续/先停"）立刻收口，不追问。
"""


def command_bootstrap_prompt(args) -> int:
    cli_path = Path(__file__).resolve()
    print(_BOOTSTRAP_PROMPT_TEMPLATE.format(cli_path=cli_path), end="")
    return 0


def command_explore(args) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit("explore requires an interactive TTY; use report flags instead")

    options = [
        ("今天总览（默认面板）", ["report", "--today"]),
        ("最近一周 token 消耗情况（去缓存后）", ["report", "--last", "7d", "--trend", "7d"]),
        ("最近一个月 token 消耗情况（去缓存后）", ["report", "--last", "30d", "--dashboard", "recent"]),
        ("按模型看今天（去缓存后）", ["report", "--today", "--by", "model"]),
        ("按项目看今天（去缓存后）", ["report", "--today", "--by", "project"]),
        ("当前会话（去缓存后）", ["report", "--today", "--current-session"]),
        ("关闭", None),
    ]

    print("Token Usage Universal · Explore")
    print("想看哪一块？")
    for index, (label, _) in enumerate(options, start=1):
        print(f"{index}. {label}")

    raw_choice = input("输入编号: ").strip()
    try:
        selected = options[int(raw_choice) - 1][1]
    except (ValueError, IndexError) as exc:
        raise SystemExit("invalid explore selection") from exc

    if selected is None:
        print("已关闭。")
        return 0

    parser = build_parser()
    selected_args = parser.parse_args(selected)
    return selected_args.func(selected_args)


def command_targets(args) -> int:
    payload = build_top20_registry_payload()
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_targets(payload))
    return 0


def _release_evidence_focus_source_ids(results: list[SourceCollectResult], registry: dict[str, object]) -> list[str]:
    priority = [
        "codex",
        "claude-code",
        "claude-desktop",
        "opencode",
        "minimax-agent",
        "qwen-code-cli",
        "kimi-cli",
        "gemini-cli",
    ]
    source_ids: list[str] = [source_id for source_id in priority if source_id in registry]
    for result in results:
        detection = result.detection
        if detection.available and detection.source_id not in source_ids:
            source_ids.append(detection.source_id)
    return source_ids


def _build_release_evidence_bundle(
    *,
    registry: dict[str, object],
    source_results: list[SourceCollectResult],
    health_payload: dict[str, object],
    targets_payload: dict[str, object],
    release_gate_payload: dict[str, object],
) -> dict[str, object]:
    report_today_window = build_time_window(today=True, last=None, start=None, end=None, tz_name=None)
    report_recent_window = build_time_window(today=False, last="30d", start=None, end=None, tz_name=None)

    default_adapters = [adapter for adapter in registry.values() if getattr(adapter, "default_selected", True)]
    report_today_results = _collect_results(report_today_window, default_adapters)
    report_recent_results = _collect_results(report_recent_window, default_adapters, chart_mode=True)

    report_today_payload = build_report(
        report_today_results,
        window=report_today_window,
        group_by=None,
        limit=5,
    )
    report_recent_payload = build_report(
        report_recent_results,
        window=report_recent_window,
        group_by="day",
        limit=10,
        trend="30d",
        chart_results=report_recent_results,
        dashboard_mode="recent",
    )

    focus_source_ids = _release_evidence_focus_source_ids(source_results, registry)
    diagnose_window = report_recent_window
    diagnose_payloads: dict[str, object] = {}
    for source_id in focus_source_ids:
        adapter = registry[source_id]
        result = adapter.collect(diagnose_window)
        result.verification_issues.extend(verify_result(result))
        diagnose_payloads[source_id] = result.as_dict()

    return {
        "metadata": {
            "cwd": str(Path.cwd()),
            "focus_source_ids": focus_source_ids,
            "today_window": report_today_window.as_dict(),
            "recent_window": report_recent_window.as_dict(),
        },
        "health": health_payload,
        "sources": [item.as_dict() for item in source_results],
        "targets": targets_payload,
        "release_gate": release_gate_payload,
        "report_today": report_today_payload,
        "report_recent_30d": report_recent_payload,
        "diagnose": diagnose_payloads,
    }


def _render_release_evidence_summary(bundle: dict[str, object]) -> str:
    release_summary = bundle["release_gate"]["summary"]
    release_metrics = bundle["release_gate"]["metrics"]
    state_summary = bundle["release_gate"].get("source_state_summary") or {}
    baseline = bundle["release_gate"].get("baseline") or {}
    baseline_diff = baseline.get("diff") or {}
    today_summary = bundle["report_today"]["summary"]
    recent_summary = bundle["report_recent_30d"]["summary"]
    lines = [
        "# Release Evidence Bundle",
        "",
        f"- cwd: `{bundle['metadata']['cwd']}`",
        f"- release-gate: `{release_summary['status']}` ({release_summary['passed_gates']}/{release_summary['total_gates']})",
        f"- Top20 coverage: `{release_metrics['coverage_ratio'] * 100:.1f}%`",
        f"- exact surface coverage: `{release_metrics['exact_surface_ratio'] * 100:.1f}%`",
        f"- default duplicate probe: `{release_metrics['default_duplicate_event_ratio'] * 100:.1f}%`",
        f"- macOS root matrix: `{release_metrics['macos_root_coverage_ratio'] * 100:.1f}%`",
        f"- Windows root matrix: `{release_metrics['windows_root_coverage_ratio'] * 100:.1f}%`",
        f"- Linux root matrix: `{release_metrics['linux_root_coverage_ratio'] * 100:.1f}%`",
        f"- report today total_tokens: `{today_summary['total_tokens']}`",
        f"- report 30d total_tokens: `{recent_summary['total_tokens']}`",
        "",
        "## Source State Summary",
        "",
        "| exact | diagnose | unsupported |",
        "|---|---|---|",
        f"| {int(state_summary.get('exact', 0))} | {int(state_summary.get('diagnose', 0))} | {int(state_summary.get('unsupported', 0))} |",
        "",
    ]
    if baseline_diff:
        lines.extend(
            [
                "## Baseline Diff",
                "",
                f"- baseline: `{baseline.get('path', '(unknown)')}`",
                f"- regressed: `{baseline_diff['counts']['regressed']}`",
                f"- improved: `{baseline_diff['counts']['improved']}`",
                f"- new sources: `{baseline_diff['counts']['new_sources']}`",
                f"- removed sources: `{baseline_diff['counts']['removed_sources']}`",
            ]
        )
        for label, key in (
            ("regressed_ids", "regressed"),
            ("improved_ids", "improved"),
            ("new_source_ids", "new_sources"),
            ("removed_source_ids", "removed_sources"),
        ):
            values = baseline_diff.get(key) or []
            if values:
                lines.append(f"- {label}: `{', '.join(values)}`")
        lines.append("")
    lines.extend(
        [
        "## Files",
        "",
        "- `release_gate.json`",
        "- `health.json`",
        "- `sources.json`",
        "- `targets.json`",
        "- `report_today.json`",
        "- `report_recent_30d.json`",
        "- `diagnose/*.json`",
        ]
    )
    if baseline_diff:
        lines.append("- `diff.json`")
    return "\n".join(lines) + "\n"


def _write_release_evidence_bundle(output_dir: Path, bundle: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnose_dir = output_dir / "diagnose"
    diagnose_dir.mkdir(parents=True, exist_ok=True)

    top_level_files = {
        "metadata.json": bundle["metadata"],
        "health.json": bundle["health"],
        "sources.json": bundle["sources"],
        "targets.json": bundle["targets"],
        "release_gate.json": bundle["release_gate"],
        "report_today.json": bundle["report_today"],
        "report_recent_30d.json": bundle["report_recent_30d"],
    }
    baseline = bundle["release_gate"].get("baseline") or {}
    if baseline.get("diff"):
        top_level_files["diff.json"] = baseline["diff"]
    for filename, payload in top_level_files.items():
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

    for source_id, payload in bundle["diagnose"].items():
        (diagnose_dir / f"{source_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

    (output_dir / "SUMMARY.md").write_text(
        _render_release_evidence_summary(bundle),
        encoding="utf-8",
    )


def command_release_gate(args) -> int:
    registry = _build_adapters()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    health = build_health_report(results)
    targets_payload = build_top20_registry_payload()
    source_states = [
        _source_status_payload_from_result(
            result,
            in_default_rollup=getattr(registry[result.detection.source_id], "default_selected", True),
        )
        for result in results
    ]
    payload = build_release_gate_payload(
        adapter_source_ids=set(registry.keys()),
        health_report=health,
        source_states=source_states,
    )
    if args.baseline:
        baseline_path = Path(args.baseline).expanduser().resolve()
        baseline_payload = _load_release_gate_baseline(baseline_path)
        payload["baseline"] = {
            "path": str(baseline_path),
            "diff": diff_against_baseline(payload, baseline_payload),
        }
    if args.output_dir:
        bundle = _build_release_evidence_bundle(
            registry=registry,
            source_results=results,
            health_payload=health,
            targets_payload=targets_payload,
            release_gate_payload=payload,
        )
        _write_release_evidence_bundle(Path(args.output_dir).expanduser(), bundle)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_release_gate(payload))
    return 0


def command_ingress_config(args) -> int:
    config = build_ingress_companion_config(
        provider=args.provider,
        upstream_base_url=args.upstream_base_url,
        protocol=args.protocol,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        local_base_path=args.local_base_path,
        log_root=args.log_root,
        project_path=args.project_path,
    )
    payload = build_ingress_companion_payload(config)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2))
    else:
        print(render_ingress_companion_payload(payload))
    return 0


def command_ingress_serve(args) -> int:
    config = build_ingress_companion_config(
        provider=args.provider,
        upstream_base_url=args.upstream_base_url,
        protocol=args.protocol,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        local_base_path=args.local_base_path,
        log_root=args.log_root,
        project_path=args.project_path,
    )
    serve_ingress_companion(config)
    return 0


def command_ingress_profiles(args) -> int:
    payload = build_ingress_profiles_payload()
    if args.format == "json":
        print(payload_to_json(payload))
    else:
        print(render_ingress_profiles_payload(payload))
    return 0


def command_ingress_bootstrap(args) -> int:
    payload = build_ingress_bootstrap_payload(
        profile_id=args.profile,
        editor=args.editor,
        upstream_base_url=args.upstream_base_url,
        model=args.model,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        local_base_path=args.local_base_path,
        log_root=args.log_root,
        project_path=args.project_path,
    )
    if args.format == "json":
        print(payload_to_json(payload))
    else:
        print(render_ingress_bootstrap_payload(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone CLI runtime for token-usage-universal"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_window_args(command):
        command.add_argument("--today", action="store_true", help="use local today window")
        command.add_argument("--last", help="relative window like 7d or 12h")
        command.add_argument("--start", help="custom window start in ISO format")
        command.add_argument("--end", help="custom window end in ISO format")
        command.add_argument("--tz", help="IANA timezone like US/Pacific")

    report = subparsers.add_parser("report", help="render usage report")
    add_window_args(report)
    report.add_argument("--source", action="append", help="limit to a source id")
    report.add_argument("--by", choices=("source", "model", "project", "session", "day"), help="extra grouping")
    report.add_argument("--trend", choices=("7d", "30d"), help="render a daily sparkline trend view")
    report.add_argument("--calendar", choices=("month",), help="render a calendar view")
    report.add_argument("--month", help="calendar month in YYYY-MM")
    report.add_argument("--dashboard", choices=("auto", "today", "recent"), help="render a richer dashboard profile")
    report.add_argument("--current-session", action="store_true", help="highlight the latest active session")
    report.add_argument("--session", help="show one session detail by session id")
    report.add_argument("--estimated-cost", action="store_true", help="show estimated cost labels explicitly")
    report.add_argument("--plain-ascii", action="store_true", help="render charts without unicode blocks")
    report.add_argument("--limit", type=int, default=5, help="row limit per section")
    report.add_argument("--format", choices=("ascii", "json"), default="ascii")
    report.set_defaults(func=command_report)

    sources = subparsers.add_parser("sources", help="list source availability")
    add_window_args(sources)
    sources.add_argument("--format", choices=("ascii", "json"), default="ascii")
    sources.set_defaults(func=command_sources)

    health = subparsers.add_parser("health", help="run onboarding self-check")
    health.add_argument("--format", choices=("ascii", "json"), default="ascii")
    health.set_defaults(func=command_health)

    diagnose = subparsers.add_parser("diagnose", help="diagnose one source")
    add_window_args(diagnose)
    diagnose.add_argument("--source", required=True, help="source id to diagnose")
    diagnose.add_argument("--format", choices=("ascii", "json"), default="ascii")
    diagnose.set_defaults(func=command_diagnose)

    targets = subparsers.add_parser("targets", help="show the frozen Top20 ecosystem registry")
    targets.add_argument("--format", choices=("ascii", "json"), default="ascii")
    targets.set_defaults(func=command_targets)

    release_gate = subparsers.add_parser("release-gate", help="evaluate the current automated release gates")
    release_gate.add_argument("--format", choices=("ascii", "json"), default="ascii")
    release_gate.add_argument("--output-dir", help="optional directory to write a release evidence bundle")
    release_gate.add_argument("--baseline", help="optional previous release evidence bundle directory for diffing")
    release_gate.set_defaults(func=command_release_gate)

    ingress = subparsers.add_parser("ingress", help="run or inspect the local ingress companion for IDE/CLI capture")
    ingress_subparsers = ingress.add_subparsers(dest="ingress_command", required=True)

    ingress_config = ingress_subparsers.add_parser("config", help="print local proxy configuration for one provider")
    ingress_config.add_argument("--provider", required=True, help="provider family id, such as deepseek, qwen, anthropic")
    ingress_config.add_argument("--upstream-base-url", required=True, help="upstream API base URL")
    ingress_config.add_argument("--protocol", choices=("openai", "anthropic", "generic"), default="openai")
    ingress_config.add_argument("--listen-host", default="127.0.0.1")
    ingress_config.add_argument("--listen-port", type=int, default=8787)
    ingress_config.add_argument("--local-base-path", help="optional local base path override, for example /v1")
    ingress_config.add_argument("--log-root", help="optional log root override")
    ingress_config.add_argument("--project-path", help="optional project path to stamp onto ingress records")
    ingress_config.add_argument("--format", choices=("text", "json"), default="text")
    ingress_config.set_defaults(func=command_ingress_config)

    ingress_serve = ingress_subparsers.add_parser("serve", help="start the local ingress companion")
    ingress_serve.add_argument("--provider", required=True, help="provider family id, such as deepseek, qwen, anthropic")
    ingress_serve.add_argument("--upstream-base-url", required=True, help="upstream API base URL")
    ingress_serve.add_argument("--protocol", choices=("openai", "anthropic", "generic"), default="openai")
    ingress_serve.add_argument("--listen-host", default="127.0.0.1")
    ingress_serve.add_argument("--listen-port", type=int, default=8787)
    ingress_serve.add_argument("--local-base-path", help="optional local base path override, for example /v1")
    ingress_serve.add_argument("--log-root", help="optional log root override")
    ingress_serve.add_argument("--project-path", help="optional project path to stamp onto ingress records")
    ingress_serve.set_defaults(func=command_ingress_serve)

    ingress_profiles = ingress_subparsers.add_parser("profiles", help="list built-in ingress bootstrap profiles")
    ingress_profiles.add_argument("--format", choices=("text", "json"), default="text")
    ingress_profiles.set_defaults(func=command_ingress_profiles)

    ingress_bootstrap = ingress_subparsers.add_parser("bootstrap", help="print IDE/CLI bootstrap snippets for one ingress profile")
    ingress_bootstrap.add_argument("--profile", required=True, help="bootstrap profile id, such as deepseek, qianfan, hunyuan, sensenova")
    ingress_bootstrap.add_argument("--editor", choices=("vscode", "jetbrains"), default="vscode")
    ingress_bootstrap.add_argument("--upstream-base-url", help="optional upstream base URL override")
    ingress_bootstrap.add_argument("--model", help="optional model override for the IDE snippet")
    ingress_bootstrap.add_argument("--listen-host", default="127.0.0.1")
    ingress_bootstrap.add_argument("--listen-port", type=int, default=8787)
    ingress_bootstrap.add_argument("--local-base-path", help="optional local base path override")
    ingress_bootstrap.add_argument("--log-root", help="optional log root override")
    ingress_bootstrap.add_argument("--project-path", help="optional project path to stamp onto ingress records")
    ingress_bootstrap.add_argument("--format", choices=("text", "json"), default="text")
    ingress_bootstrap.set_defaults(func=command_ingress_bootstrap)

    explore = subparsers.add_parser("explore", help="interactive dashboard launcher")
    explore.set_defaults(func=command_explore)

    bootstrap_prompt = subparsers.add_parser(
        "bootstrap-prompt",
        help="print a copy-paste cold-start prompt for hosts without skill loader",
    )
    bootstrap_prompt.set_defaults(func=command_bootstrap_prompt)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
