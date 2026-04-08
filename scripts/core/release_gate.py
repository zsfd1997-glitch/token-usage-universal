from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from adapters.chromium_desktop_family import build_chromium_desktop_family_adapters
from adapters.claude_desktop import ClaudeDesktopAdapter
from adapters.compatible_api_family import GenericOpenAICompatibleAdapter, build_provider_api_adapters
from adapters.minimax_agent import MiniMaxAgentAdapter
from core.config import (
    TOKEN_USAGE_DISCOVERY_ROOTS_ENV,
    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
    default_claude_local_agent_root,
    default_desktop_app_roots,
    default_minimax_agent_root,
    default_opencode_roots,
)
from core.ecosystem_registry import build_top20_registry_payload
from core.models import TimeWindow, UsageEvent


EXPECTED_TOTAL_ECOSYSTEMS = 20
EXPECTED_CHINA_PRIORITY_ECOSYSTEMS = 13
EXPECTED_TOTAL_SURFACES = 60


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _make_gate(
    gate_id: str,
    label: str,
    *,
    passed: bool,
    actual: str,
    threshold: str,
    evidence: str,
) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "label": label,
        "status": "pass" if passed else "fail",
        "actual": actual,
        "threshold": threshold,
        "evidence": evidence,
    }


def _collect_claimed_source_ids(payload: dict[str, object]) -> tuple[list[str], list[str]]:
    adapter_backed_source_ids: list[str] = []
    all_claimed_source_ids: list[str] = []
    for ecosystem in payload["ecosystems"]:
        provider_ids = [str(item) for item in ecosystem.get("provider_source_ids") or []]
        adapter_backed_source_ids.extend(provider_ids)
        all_claimed_source_ids.extend(provider_ids)
        for surface in ecosystem["surfaces"]:
            implemented_source_ids = [str(item) for item in surface.get("implemented_source_ids") or []]
            all_claimed_source_ids.extend(implemented_source_ids)
            if surface["primary_lane"] != "ingress-capture":
                adapter_backed_source_ids.extend(implemented_source_ids)
    return adapter_backed_source_ids, all_claimed_source_ids


def _probe_window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Release Gate Probe Window",
        timezone_name="US/Pacific",
    )


def _event_fingerprint(event: UsageEvent) -> tuple[str, str, str, int, str | None]:
    return (
        event.timestamp.isoformat(),
        event.session_id,
        event.source_path,
        int(event.total_tokens),
        event.raw_model or event.model,
    )


def _duplicate_event_ratio(events: list[UsageEvent]) -> float:
    if not events:
        return 0.0
    unique = {_event_fingerprint(event) for event in events}
    duplicates = len(events) - len(unique)
    return _ratio(duplicates, len(events))


def _build_default_selection_duplicate_probe() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_file = root / "provider-overlap.jsonl"
        log_file.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "created_at": "2026-03-25T10:00:00-07:00",
                            "provider": "openai",
                            "model": "gpt-5.4",
                            "session_id": "oa-1",
                            "usage": {"input_tokens": 100, "output_tokens": 25, "total_tokens": 125},
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-03-25T10:05:00-07:00",
                            "provider": "moonshot",
                            "model": "kimi-k2",
                            "session_id": "ms-1",
                            "usage": {"prompt_tokens": 90, "completion_tokens": 30, "total_tokens": 120},
                        }
                    ),
                    json.dumps(
                        {
                            "created_at": "2026-03-25T10:10:00-07:00",
                            "provider": "custom-lab",
                            "model": "lab-1",
                            "session_id": "lab-1",
                            "usage": {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50},
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        adapters = [*build_provider_api_adapters(), GenericOpenAICompatibleAdapter()]
        with patch.dict(
            os.environ,
            {
                TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                TOKEN_USAGE_DISCOVERY_ROOTS_ENV: str(root / "unused"),
            },
            clear=False,
        ):
            default_results = [
                adapter.collect(_probe_window())
                for adapter in adapters
                if getattr(adapter, "default_selected", True)
            ]
            explicit_results = [adapter.collect(_probe_window()) for adapter in adapters]

    default_events = [event for result in default_results for event in result.events]
    explicit_events = [event for result in explicit_results for event in result.events]
    return {
        "default_selected_source_ids": [adapter.source_id for adapter in adapters if getattr(adapter, "default_selected", True)],
        "manual_only_source_ids": [adapter.source_id for adapter in adapters if not getattr(adapter, "default_selected", True)],
        "default_total_events": len(default_events),
        "explicit_total_events": len(explicit_events),
        "default_duplicate_event_ratio": _duplicate_event_ratio(default_events),
        "explicit_duplicate_event_ratio": _duplicate_event_ratio(explicit_events),
        "default_sessions": sorted({event.session_id for event in default_events}),
        "explicit_sessions": sorted({event.session_id for event in explicit_events}),
    }


def _platform_source_matrix(
    *,
    home: Path,
    os_name: str,
    platform_name: str,
    appdata: str | None = None,
    localappdata: str | None = None,
) -> dict[str, dict[str, object]]:
    desktop_adapters = [ClaudeDesktopAdapter(), MiniMaxAgentAdapter(), *build_chromium_desktop_family_adapters()]
    sources: dict[str, dict[str, object]] = {
        "codex": {
            "paths": [str(home / ".codex" / "sessions")],
        },
        "claude-code": {
            "paths": [
                str(home / ".claude" / "transcripts"),
                str(
                    default_claude_local_agent_root(
                        os_name=os_name,
                        home=home,
                        appdata=appdata,
                    )
                ),
            ],
        },
        "opencode": {
            "paths": [
                str(path)
                for path in default_opencode_roots(
                    os_name=os_name,
                    home=home,
                    appdata=appdata,
                    localappdata=localappdata,
                    platform_name=platform_name,
                )
            ],
        },
        "qwen-code-cli": {
            "paths": [str(home / ".qwen")],
        },
        "kimi-cli": {
            "paths": [str(home / ".kimi")],
        },
        "gemini-cli": {
            "paths": [str(home / ".gemini")],
        },
    }

    for adapter in desktop_adapters:
        definition = adapter.definition
        if definition.source_id == "minimax-agent":
            paths = [
                str(
                    default_minimax_agent_root(
                        os_name=os_name,
                        home=home,
                        appdata=appdata,
                        platform_name=platform_name,
                    )
                )
            ]
        else:
            paths = [
                str(path)
                for path in default_desktop_app_roots(
                    definition.app_names,
                    os_name=os_name,
                    home=home,
                    appdata=appdata,
                    localappdata=localappdata,
                    platform_name=platform_name,
                )
            ]
        sources[definition.source_id] = {"paths": paths}

    for payload in sources.values():
        paths = [path for path in payload["paths"] if str(path).strip()]
        payload["paths"] = paths
        payload["ok"] = bool(paths)
    return sources


def _build_platform_matrix() -> dict[str, object]:
    macos_sources = _platform_source_matrix(
        home=Path("/Users/example"),
        os_name="posix",
        platform_name="darwin",
    )
    windows_sources = _platform_source_matrix(
        home=Path("C:/Users/example"),
        os_name="nt",
        platform_name="win32",
        appdata="C:/Users/example/AppData/Roaming",
        localappdata="C:/Users/example/AppData/Local",
    )
    macos_total = len(macos_sources)
    windows_total = len(windows_sources)
    macos_ok = sum(1 for item in macos_sources.values() if item["ok"])
    windows_ok = sum(1 for item in windows_sources.values() if item["ok"])
    return {
        "macos": {
            "supported": macos_ok == macos_total,
            "covered_sources": macos_ok,
            "total_sources": macos_total,
            "coverage_ratio": _ratio(macos_ok, macos_total),
            "evidence_scope": "root-aware-source-matrix",
            "sources": macos_sources,
        },
        "windows": {
            "supported": windows_ok == windows_total,
            "covered_sources": windows_ok,
            "total_sources": windows_total,
            "coverage_ratio": _ratio(windows_ok, windows_total),
            "evidence_scope": "root-aware-source-matrix",
            "sources": windows_sources,
        },
    }


def build_release_gate_payload(
    *,
    adapter_source_ids: set[str],
    health_report: dict[str, object],
) -> dict[str, object]:
    registry_payload = build_top20_registry_payload()
    summary = registry_payload["summary"]

    coverage_ratio = _ratio(int(summary["total_ecosystems"]), EXPECTED_TOTAL_ECOSYSTEMS)
    china_priority_ratio = _ratio(int(summary["china_priority_ecosystems"]), EXPECTED_CHINA_PRIORITY_ECOSYSTEMS)
    exact_surface_ratio = _ratio(int(summary["surface_maturity"].get("exact-ready", 0)), int(summary["total_surfaces"]))

    adapter_backed_source_ids, all_claimed_source_ids = _collect_claimed_source_ids(registry_payload)
    missing_backing_source_ids = sorted(source_id for source_id in adapter_backed_source_ids if source_id not in adapter_source_ids)

    detections = [item for item in health_report.get("sources", []) if item.get("supported")]
    explainable_detections = [item for item in detections if str(item.get("summary", "")).strip()]
    diagnose_explainability_ratio = _ratio(len(explainable_detections), len(detections))

    duplicate_probe = _build_default_selection_duplicate_probe()
    default_duplicate_event_ratio = float(duplicate_probe["default_duplicate_event_ratio"])

    platform_matrix = _build_platform_matrix()
    platform_ready = bool(platform_matrix["macos"]["supported"]) and bool(platform_matrix["windows"]["supported"])

    gates = [
        _make_gate(
            "top20-coverage",
            "Top20 覆盖率 >= 90%",
            passed=coverage_ratio >= 0.9,
            actual=f"{summary['total_ecosystems']}/{EXPECTED_TOTAL_ECOSYSTEMS} ({_percent(coverage_ratio)})",
            threshold=">= 90.0%",
            evidence="Registry 已冻结 20/20 个生态。",
        ),
        _make_gate(
            "china-priority-coverage",
            "中国优先 13 覆盖率 = 100%",
            passed=china_priority_ratio >= 1.0,
            actual=f"{summary['china_priority_ecosystems']}/{EXPECTED_CHINA_PRIORITY_ECOSYSTEMS} ({_percent(china_priority_ratio)})",
            threshold="= 100.0%",
            evidence="中国优先生态已全部入表。",
        ),
        _make_gate(
            "exact-surface-coverage",
            "exact 覆盖率 >= 80%",
            passed=exact_surface_ratio >= 0.8,
            actual=f"{summary['surface_maturity'].get('exact-ready', 0)}/{summary['total_surfaces']} ({_percent(exact_surface_ratio)})",
            threshold=">= 80.0%",
            evidence="当前 60/60 surface 已是 exact-ready。",
        ),
        _make_gate(
            "false-ready-claims",
            "结构性误报 ready = 0",
            passed=not missing_backing_source_ids,
            actual=f"{len(missing_backing_source_ids)} missing adapter-backed claims",
            threshold="= 0",
            evidence="provider/native-client 这两类 claim 都要求存在真实 adapter 背书。",
        ),
        _make_gate(
            "default-report-duplicate-rate",
            "默认 report 重复计数率 <= 0.5%",
            passed=default_duplicate_event_ratio <= 0.005,
            actual=(
                f"{duplicate_probe['default_total_events']} events / "
                f"{_percent(default_duplicate_event_ratio)} duplicates"
            ),
            threshold="<= 0.5%",
            evidence="使用临时 exact log 同时命中 provider family 与 generic fallback，验证默认 report 路径不会重复统计。",
        ),
        _make_gate(
            "diagnose-explainability",
            "diagnose 可解释率 >= 95%",
            passed=diagnose_explainability_ratio >= 0.95,
            actual=f"{len(explainable_detections)}/{len(detections)} ({_percent(diagnose_explainability_ratio)})",
            threshold=">= 95.0%",
            evidence="以 health 返回的 supported source summary 是否可读作为 explainability 代理指标。",
        ),
        _make_gate(
            "windows-macos-root-matrix",
            "Windows + macOS root matrix = 100%",
            passed=platform_ready,
            actual=(
                f"macOS {platform_matrix['macos']['covered_sources']}/{platform_matrix['macos']['total_sources']} "
                f"windows {platform_matrix['windows']['covered_sources']}/{platform_matrix['windows']['total_sources']}"
            ),
            threshold="both 100%",
            evidence="当前自动验证所有 root-aware source 的双平台默认根路径矩阵。",
        ),
    ]

    passed_gates = [item for item in gates if item["status"] == "pass"]
    failed_gates = [item for item in gates if item["status"] != "pass"]

    return {
        "summary": {
            "status": "pass" if not failed_gates else "fail",
            "passed_gates": len(passed_gates),
            "failed_gates": len(failed_gates),
            "total_gates": len(gates),
            "evidence_scope": "registry + health + runtime-duplicate-probe + root-aware-source-matrix",
        },
        "metrics": {
            "coverage_ratio": coverage_ratio,
            "china_priority_ratio": china_priority_ratio,
            "exact_surface_ratio": exact_surface_ratio,
            "default_duplicate_event_ratio": default_duplicate_event_ratio,
            "diagnose_explainability_ratio": diagnose_explainability_ratio,
            "macos_root_coverage_ratio": float(platform_matrix["macos"]["coverage_ratio"]),
            "windows_root_coverage_ratio": float(platform_matrix["windows"]["coverage_ratio"]),
        },
        "gates": gates,
        "registry_summary": summary,
        "platform_matrix": platform_matrix,
        "duplicate_probe": duplicate_probe,
        "missing_backing_source_ids": missing_backing_source_ids,
        "all_claimed_source_ids": all_claimed_source_ids,
        "notes": [
            "release-gate 现在会实跑默认 report 的重复计数 probe，并验证所有 root-aware source 的双平台默认根路径矩阵。",
            "真实双机 app-data 命中与大样本重复计数实测仍建议在正式对外发布前补跑。",
        ],
    }
