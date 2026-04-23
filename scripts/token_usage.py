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

# Slimmed adapter set (v1.2): the user's workflow is 100% through the
# Aliyun DashScope 百炼 URL, with opencode + trae as UI shells. All
# per-provider adapters (qwen-api / zhipu-glm-api / moonshot-kimi-api /
# ...), per-client adapters (claude-code / codex / kimi-cli / gemini-cli /
# qwen-code-cli), and chromium-desktop-family members don't match the
# actual request path — they live in _archive/adapters/ and can be
# restored if the scope expands. Model-level breakdowns still work
# because opencode records modelID per message; you don't need a
# per-provider adapter to see "glm-4.5 used X tokens today".
from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from adapters.opencode import OpenCodeAdapter
from adapters.trae import TraeAdapter
from ascii_hifi import render_diagnose, render_health, render_report, render_sources
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
from core.models import SourceCollectResult
from core.time_window import build_month_window, build_time_window, within_window
from core.verifier import verify_result


def _build_full_registry():
    """Return the active adapter registry. v1.2 slimmed it down to the
    three that match the deployment's actual request path: opencode CLI
    (main UI shell), trae (desktop UI with optional ingress), and the
    generic-openai-compatible fallback that catches anything written to
    a user-declared JSONL via TOKEN_USAGE_GENERIC_LOG_GLOBS (ingress
    companion output lands here too)."""
    adapters = [
        OpenCodeAdapter(),
        TraeAdapter(),
        GenericOpenAICompatibleAdapter(),
    ]
    return {adapter.source_id: adapter for adapter in adapters}


def _probe_and_cache_active_sources(full_registry) -> list[str]:
    """Run detect() on every adapter and remember which ones have local
    traces. Writes the result to the environment cache file. Returns the
    list of active source IDs."""
    from core.environment_cache import pick_active_from_detections, save_active_source_ids

    detections = {sid: adapter.detect() for sid, adapter in full_registry.items()}
    active = pick_active_from_detections(detections)
    # Always keep the generic fallback adapter — it costs almost nothing
    # to instantiate and the user may add log globs after the probe.
    if "generic-openai-compatible" in full_registry and "generic-openai-compatible" not in active:
        active.append("generic-openai-compatible")
    save_active_source_ids(active)
    return active


def _build_adapters(*, use_cache: bool = True, force_refresh: bool = False, all_sources: bool = False):
    """Return the adapter registry for runtime use, optionally filtered to
    sources that have been probed active on this host.

    Resolution order (first match wins):
      1. `all_sources=True` or env `TOKEN_USAGE_ALL_SOURCES=1`    → full 51 adapters
      2. env `TOKEN_USAGE_SOURCES=a,b,c` (explicit whitelist)     → filter by whitelist
      3. `force_refresh=True`: probe now, save cache, filter       → fresh subset
      4. cache present and not expired                             → filter by cache
      5. no cache: probe now, save cache, filter                   → fresh subset

    Filtering always keeps at least the generic-openai-compatible adapter
    so a user who adds log globs after the probe still gets counted.
    """
    from core.environment_cache import (
        load_active_source_ids,
        parse_env_filter,
    )

    full = _build_full_registry()

    if all_sources or os.environ.get("TOKEN_USAGE_ALL_SOURCES", "").strip() == "1":
        return full

    env_filter = parse_env_filter(os.environ.get("TOKEN_USAGE_SOURCES", ""))
    if env_filter:
        return {sid: a for sid, a in full.items() if sid in env_filter}

    if force_refresh or not use_cache:
        active = set(_probe_and_cache_active_sources(full))
        return {sid: a for sid, a in full.items() if sid in active}

    cached = load_active_source_ids()
    if cached is None:
        # First run on this host — probe once, cache result.
        cached = set(_probe_and_cache_active_sources(full))
    return {sid: a for sid, a in full.items() if sid in cached}


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
    registry = _build_adapters(
        force_refresh=getattr(args, "refresh", False),
        all_sources=getattr(args, "all_sources", False),
    )
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
    # `sources` always shows the full 51-source panel regardless of cache;
    # users expect to see the complete supported list here.
    registry = _build_full_registry()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    if args.format == "json":
        print(json.dumps([_source_status_payload(adapter) for adapter in registry.values()], ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_sources(results))
    return 0


def command_health(args) -> int:
    # `health` IS the probe — it scans every adapter and uses the result
    # to refresh the environment cache so subsequent `report` / `diagnose`
    # calls can skip inactive sources.
    from core.environment_cache import pick_active_from_detections, save_active_source_ids

    registry = _build_full_registry()
    results = [SourceCollectResult(detection=adapter.detect()) for adapter in registry.values()]
    detections = {r.detection.source_id: r.detection for r in results}
    active_ids = pick_active_from_detections(detections)
    if "generic-openai-compatible" in registry and "generic-openai-compatible" not in active_ids:
        active_ids.append("generic-openai-compatible")
    try:
        save_active_source_ids(active_ids)
    except OSError:
        pass  # non-fatal: health still works without cache write

    health = build_health_report(results)
    if args.format == "json":
        print(json.dumps(health, ensure_ascii=_STDOUT_JSON_ENSURE_ASCII, indent=2, default=_json_default))
    else:
        print(render_health(health))
    return 0


def command_diagnose(args) -> int:
    # Diagnose must work for any source the user names, even if that
    # source isn't in the cached active set — so start from the full
    # registry.
    registry = _build_full_registry()
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


def command_probe(args) -> int:
    """One-off environment probe: detect every adapter, decide which ones
    have local traces on this host, and persist the list so future
    `report` calls only run those. Equivalent in effect to `health` but
    emits a focused summary instead of the ascii-hifi health panel."""
    from core.environment_cache import (
        environment_cache_path,
        pick_active_from_detections,
        save_active_source_ids,
    )
    import time as _time

    full = _build_full_registry()
    t0 = _time.perf_counter()
    detections = {sid: adapter.detect() for sid, adapter in full.items()}
    elapsed_ms = (_time.perf_counter() - t0) * 1000

    active = pick_active_from_detections(detections)
    if "generic-openai-compatible" in full and "generic-openai-compatible" not in active:
        active.append("generic-openai-compatible")
    path = save_active_source_ids(active)

    total = len(full)
    inactive = total - len(active)
    print(f"Token Usage Universal · Environment Probe")
    print(f"  total adapters:  {total}")
    print(f"  active on host:  {len(active)}")
    print(f"  skipped:         {inactive}")
    print(f"  probe time:      {elapsed_ms:.0f} ms")
    print(f"  cache written:   {path}")
    print()
    print("Active sources (these will run on every `report --today`):")
    for sid in sorted(active):
        detection = detections.get(sid)
        mark = "✓" if detection and getattr(detection, "available", False) else " "
        print(f"  {mark} {sid}")
    if inactive:
        print()
        print(f"Skipped {inactive} sources with no local trace on this host.")
        print("Force a re-probe any time with:  python scripts/token_usage.py probe")
        print("Or run a single report with all adapters:  report --all-sources")
    return 0


def command_locate_opencode(args) -> int:
    """Scan every plausible OpenCode storage location on this host and
    report which ones actually have session/message files — with today's
    activity if any. Use this when desktop sees tokens but CLI sees 0,
    or when `report --today` returns 0 despite active CLI usage.
    """
    from datetime import datetime, timezone, timedelta
    import os as _os

    home = Path.home()
    candidates: list[Path] = []

    if _os.name == "nt":
        for env_name in ("APPDATA", "LOCALAPPDATA"):
            base = _os.environ.get(env_name, "").strip()
            if base:
                base_path = Path(base)
                for name in ("OpenCode", "ai.opencode.desktop", "opencode",
                             "opencode-cli", "opencode_cli", "OpenCodeCLI"):
                    candidates.append(base_path / name)
        for sub in (".opencode", ".config/opencode", ".local/share/opencode",
                    ".local/state/opencode"):
            candidates.append(home / sub)
        for letter in ("C", "D", "E"):
            for rel in ("OpenCode/storage", "opencode/storage",
                        "opencode-cli/storage", "Tools/opencode/storage"):
                candidates.append(Path(f"{letter}:/") / rel / "..")
    else:
        for sub in (".opencode", ".config/opencode",
                    ".local/share/opencode", ".local/state/opencode",
                    "Library/Application Support/OpenCode",
                    "Library/Application Support/ai.opencode.desktop"):
            candidates.append(home / sub)

    extra = _os.environ.get("TOKEN_USAGE_OPENCODE_ROOTS", "").strip()
    if extra:
        for text in extra.split(","):
            if text.strip():
                candidates.append(Path(text.strip()).expanduser())

    now = datetime.now().astimezone()
    today_local = now.date()
    seen: set[str] = set()
    hits: list[dict[str, object]] = []
    for root in candidates:
        try:
            key = str(root.resolve())
        except (OSError, ValueError):
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        if not root.exists() or not root.is_dir():
            continue

        session_files: list[Path] = []
        message_files: list[Path] = []
        try:
            session_files = [p for p in root.rglob("storage/session/**/*.json") if p.is_file()][:200]
            message_files = [p for p in root.rglob("storage/message/**/*.json") if p.is_file()][:500]
        except (OSError, PermissionError):
            pass

        today_message_count = 0
        for path in message_files:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
            except OSError:
                continue
            if mtime.date() == today_local:
                today_message_count += 1

        if session_files or message_files:
            hits.append({
                "path": str(root),
                "sessions": len(session_files),
                "messages": len(message_files),
                "today_messages": today_message_count,
            })

    print("Token Usage Universal · Locate OpenCode")
    print(f"(scanned {len(seen)} candidate paths on this machine)")
    print()
    if not hits:
        print("No OpenCode storage found at any common location.")
        print("Next steps:")
        print("  1. Find your opencode-cli.exe / OpenCode.exe binary location:")
        print("     Get-Command opencode, opencode-cli -ErrorAction SilentlyContinue")
        print("  2. Look near the binary for a storage/session/ folder")
        print("  3. Set: $env:TOKEN_USAGE_OPENCODE_ROOTS = \"<that path>\"")
        print("  4. Rerun: python scripts/token_usage.py health")
        return 1

    print("Found OpenCode storage at:")
    print()
    header = f"  {'sessions':>8}  {'msgs':>6}  {'today':>6}  path"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for hit in hits:
        marker = "*" if hit["today_messages"] else " "
        print(f"{marker} {hit['sessions']:>8}  {hit['messages']:>6}  {hit['today_messages']:>6}  {hit['path']}")

    active_hits = [h for h in hits if h["today_messages"] > 0]
    print()
    if active_hits:
        print("Paths with today's activity (marked *) are where your CLI is actually writing.")
        print()
        print("To make `report --today` see all of them, set:")
        if _os.name == "nt":
            joined = ",".join(h["path"] for h in hits)
            print(f"  $env:TOKEN_USAGE_OPENCODE_ROOTS = \"{joined}\"")
        else:
            joined = ",".join(h["path"] for h in hits)
            print(f"  export TOKEN_USAGE_OPENCODE_ROOTS=\"{joined}\"")
        print()
        print("Then rerun: python scripts/token_usage.py report --today")
    else:
        print("No storage had today's activity. Either no OpenCode use today, or the")
        print("CLI writes to yet another location. Check the opencode-cli.exe install")
        print("directory directly for a self-contained storage/ subfolder.")
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
    report.add_argument(
        "--refresh",
        action="store_true",
        help="ignore the environment cache and re-probe every adapter this run (updates cache)",
    )
    report.add_argument(
        "--all-sources",
        action="store_true",
        help="bypass the environment cache and run every adapter (slow; equivalent to TOKEN_USAGE_ALL_SOURCES=1)",
    )
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

    locate_opencode = subparsers.add_parser(
        "locate-opencode",
        help="scan all plausible OpenCode storage locations and report which have today's activity (diagnose CLI-vs-desktop mismatches)",
    )
    locate_opencode.set_defaults(func=command_locate_opencode)

    probe = subparsers.add_parser(
        "probe",
        help="detect which adapters have any data on this host and cache the result (so future `report` runs skip the ~45 dead adapters)",
    )
    probe.set_defaults(func=command_probe)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
