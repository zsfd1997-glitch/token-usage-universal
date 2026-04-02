#!/usr/bin/env python3
"""Standalone CLI runtime for token-usage-universal."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.claude_code import ClaudeCodeAdapter
from adapters.compatible_api_family import build_provider_api_adapters
from adapters.codex import CodexAdapter
from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from adapters.minimax_agent import MiniMaxAgentAdapter
from adapters.opencode import OpenCodeAdapter
from ascii_hifi import render_diagnose, render_health, render_report, render_sources
from core.health import build_health_report
from core.aggregator import build_report
from core.models import SourceCollectResult
from core.time_window import build_month_window, build_time_window, within_window
from core.verifier import verify_result


def _build_adapters():
    adapters = [
        CodexAdapter(),
        ClaudeCodeAdapter(),
        OpenCodeAdapter(),
        MiniMaxAgentAdapter(),
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
        print(json.dumps({"results": [item.as_dict() for item in results], "report": report}, ensure_ascii=False, indent=2, default=_json_default))
    else:
        print(render_report(report, plain_ascii=args.plain_ascii, show_estimated_cost=(args.estimated_cost or bool(dashboard_mode))))
    return 0


def command_sources(args) -> int:
    registry = _build_adapters()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    if args.format == "json":
        print(json.dumps([item.as_dict() for item in results], ensure_ascii=False, indent=2, default=_json_default))
    else:
        print(render_sources(results))
    return 0


def command_health(args) -> int:
    registry = _build_adapters()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    health = build_health_report(results)
    if args.format == "json":
        print(json.dumps(health, ensure_ascii=False, indent=2, default=_json_default))
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
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=_json_default))
    else:
        print(render_diagnose(result, window))
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

    explore = subparsers.add_parser("explore", help="interactive dashboard launcher")
    explore.set_defaults(func=command_explore)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
