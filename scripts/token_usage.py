#!/usr/bin/env python3
"""Internal CLI core for the token-usage-universal skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.claude_code import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from ascii_hifi import render_diagnose, render_health, render_report, render_sources
from core.health import build_health_report
from core.aggregator import build_report
from core.models import SourceCollectResult
from core.time_window import build_time_window
from core.verifier import verify_result


def _build_adapters():
    adapters = [
        CodexAdapter(),
        ClaudeCodeAdapter(),
        GenericOpenAICompatibleAdapter(),
    ]
    return {adapter.source_id: adapter for adapter in adapters}


def _resolve_sources(args, registry):
    requested = args.source or []
    if not requested:
        return list(registry.values())

    selected = []
    for source_id in requested:
        adapter = registry.get(source_id)
        if not adapter:
            raise SystemExit(f"unknown source: {source_id}")
        selected.append(adapter)
    return selected


def _time_window_from_args(args):
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


def command_report(args) -> int:
    registry = _build_adapters()
    window = _time_window_from_args(args)
    results = []
    for adapter in _resolve_sources(args, registry):
        result = adapter.collect(window)
        result.verification_issues.extend(verify_result(result))
        results.append(result)

    report = build_report(
        results,
        window=window,
        group_by=args.by,
        limit=args.limit,
    )
    if args.format == "json":
        print(json.dumps({"results": [item.as_dict() for item in results], "report": report}, ensure_ascii=False, indent=2, default=_json_default))
    else:
        print(render_report(report))
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Internal CLI core for the token-usage-universal skill"
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
    report.add_argument("--by", choices=("source", "model", "project", "session"), help="extra grouping")
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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
