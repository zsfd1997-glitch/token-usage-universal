from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ascii_hifi import render_diagnose, render_report
from core.aggregator import build_report
from core.models import SourceCollectResult, SourceDetection, TimeWindow, UsageEvent


def _make_window(days: float = 1.0) -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    end = datetime(2026, 3, 25, 12, 0, tzinfo=tzinfo)
    start = end - timedelta(days=days)
    return TimeWindow(
        start=start,
        end=end,
        label="Test Window",
        timezone_name="US/Pacific",
    )


def _make_result(
    total_tokens: int,
    *,
    source: str = "codex",
    model: str = "gpt-5.4",
    provider: str = "openai",
    session_id: str | None = None,
    timestamp: datetime | None = None,
) -> SourceCollectResult:
    event = UsageEvent(
        source=source,
        provider=provider,
        timestamp=timestamp or datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("US/Pacific")),
        session_id=session_id or f"{source}-session-1",
        project_path="/tmp/example",
        model=model,
        input_tokens=total_tokens,
        cached_input_tokens=int(total_tokens * 0.2),
        output_tokens=int(total_tokens * 0.05),
        reasoning_tokens=int(total_tokens * 0.01),
        total_tokens=total_tokens,
        accuracy_level="exact",
        raw_event_kind="unit-test",
        source_path="/tmp/source.jsonl",
    )
    detection = SourceDetection(
        source_id=source,
        display_name=source,
        provider=provider,
        accuracy_level="exact",
        supported=True,
        available=True,
        summary="ready",
    )
    return SourceCollectResult(detection=detection, events=[event], scanned_files=1)


def _make_unavailable_result(
    *,
    source: str = "claude-code",
    provider: str = "anthropic",
    summary: str = "timing.json not found",
) -> SourceCollectResult:
    detection = SourceDetection(
        source_id=source,
        display_name=source,
        provider=provider,
        accuracy_level="exact",
        supported=True,
        available=False,
        summary=summary,
    )
    return SourceCollectResult(detection=detection, events=[], scanned_files=0)


class ReportingTests(unittest.TestCase):
    def test_insights_include_latest_model_anchors(self) -> None:
        report = build_report([_make_result(12_000_000)], window=_make_window(), group_by=None, limit=5)
        insights = report["insights"]

        self.assertEqual(insights["model_anchor_openai"], "OpenAI GPT-5.3-Codex / GPT-5.4")
        self.assertEqual(insights["model_anchor_anthropic"], "Anthropic Opus 4.5 / Opus 4.6")
        self.assertEqual(insights["model_anchor_verified_at"], "2026-03-25")

    def test_ascii_report_uses_terminal_dashboard_language(self) -> None:
        report = build_report([_make_result(120_000_000)], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report, show_estimated_cost=True)

        self.assertIn("Token 用量", rendered)
        self.assertIn("费用", rendered)
        self.assertIn("当前会话", rendered)
        self.assertIn("去缓存后", rendered)
        self.assertIn("总 token", rendered)
        self.assertIn("用量", rendered)
        self.assertNotIn("按去缓存后 token", rendered)
        self.assertNotIn("概览", rendered)
        self.assertNotIn("最后更新", rendered)
        self.assertNotIn("速读", rendered)
        self.assertNotIn("等级评定", rendered)
        self.assertNotIn("诊断", rendered)

    def test_company_realm_thresholds(self) -> None:
        cases = [
            (9_999_999, "练气"),
            (10_000_000, "筑基"),
            (99_999_999, "筑基"),
            (100_000_000, "金丹"),
            (499_999_999, "金丹"),
            (500_000_000, "元婴"),
            (1_999_999_999, "元婴"),
            (2_000_000_000, "化神"),
        ]
        for tokens, expected in cases:
            with self.subTest(tokens=tokens):
                report = build_report([_make_result(tokens)], window=_make_window(), group_by=None, limit=5)
                self.assertEqual(report["insights"]["realm_name"], expected)

    def test_daily_equivalent_normalizes_multi_day_window(self) -> None:
        report = build_report([_make_result(700_000_000)], window=_make_window(days=7.0), group_by=None, limit=5)
        insights = report["insights"]

        self.assertEqual(insights["daily_equivalent_tokens"], 100_000_000)
        self.assertEqual(insights["realm_name"], "金丹")

    def test_benchmark_examples_are_exposed_in_json_report(self) -> None:
        report = build_report([_make_result(12_000_000)], window=_make_window(), group_by=None, limit=5)

        self.assertGreaterEqual(len(report["benchmark_examples"]), 4)
        names = [item["source_name"] for item in report["benchmark_examples"]]
        self.assertIn("Manage costs effectively", names)
        self.assertIn("Introducing GPT-5.4", names)

    def test_report_groups_usage_by_model(self) -> None:
        report = build_report(
            [
                _make_result(12_000_000, source="codex", model="gpt-5.4"),
                _make_result(8_000_000, source="generic-openai-compatible", model="deepseek-chat", provider="openai-compatible"),
            ],
            window=_make_window(),
            group_by="model",
            limit=5,
        )

        self.assertEqual(report["summary"]["models"], 2)
        self.assertEqual(report["by_model"][0]["name"], "gpt-5.4")
        self.assertEqual(report["by_model"][1]["name"], "deepseek-chat")

    def test_report_surfaces_observed_models_not_counted_in_exact_usage(self) -> None:
        observed = _make_unavailable_result(
            source="claude-desktop",
            summary="Claude Desktop desktop traces detected, but no exact token payloads were present in the current snapshot",
        )
        observed.detection.details.append("detected model traces in desktop stores: claude-sonnet-4-6")

        report = build_report([_make_result(12_000_000, model="gpt-5.4"), observed], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report, show_estimated_cost=True)

        self.assertEqual(
            report["observed_only_models"],
            [{"name": "claude-sonnet-4-6", "sources": ["claude-desktop"], "evidence": "model-trace-only"}],
        )
        self.assertEqual(report["summary"]["observed_only_models"], 1)
        self.assertIn("已观测模型（未计入 token）", rendered)
        self.assertIn("claude-sonnet-4-6", rendered)
        self.assertIn("当前无 exact token payload", rendered)

    def test_report_surfaces_observed_sources_not_counted_in_exact_usage(self) -> None:
        observed = _make_unavailable_result(
            source="minimax-agent",
            provider="minimax",
            summary="MiniMax Agent desktop traces detected, but no exact token payloads were present in the current snapshot",
        )
        observed.detection.display_name = "MiniMax Agent"
        observed.scanned_files = 51

        report = build_report([_make_result(12_000_000, model="gpt-5.4"), observed], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report, show_estimated_cost=True)

        self.assertEqual(
            report["observed_only_sources"],
            [
                {
                    "source_id": "minimax-agent",
                    "display_name": "MiniMax Agent",
                    "reason": "MiniMax Agent desktop traces detected, but no exact token payloads were present in the current snapshot",
                    "files": 51,
                }
            ],
        )
        self.assertEqual(report["summary"]["observed_only_sources"], 1)
        self.assertIn("观测层", rendered)
        self.assertIn("未计量来源 1", rendered)
        self.assertIn("避免静默漏掉", rendered)
        self.assertIn("已观测来源（未计入 token）", rendered)
        self.assertIn("minimax-agent", rendered)
        self.assertIn("MiniMax Agent", rendered)

    def test_effective_tokens_are_exposed_in_summary_and_groups(self) -> None:
        report = build_report([_make_result(10_000_000)], window=_make_window(), group_by="model", limit=5)

        self.assertEqual(report["summary"]["effective_tokens"], 8_000_000)
        self.assertEqual(report["by_model"][0]["effective_tokens"], 8_000_000)

    def test_by_day_groups_across_dates(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        older = _make_result(
            5_000_000,
            timestamp=datetime(2026, 3, 24, 9, 0, tzinfo=tzinfo),
            session_id="s-1",
        )
        newer = _make_result(
            7_000_000,
            timestamp=datetime(2026, 3, 25, 11, 0, tzinfo=tzinfo),
            session_id="s-2",
        )
        report = build_report([older, newer], window=_make_window(days=2.0), group_by="day", limit=5)

        self.assertEqual([row["date"] for row in report["by_day"]], ["2026-03-24", "2026-03-25"])
        self.assertEqual(report["by_day"][-1]["total_tokens"], 7_000_000)
        self.assertEqual(report["by_day"][-1]["effective_tokens"], 5_600_000)

    def test_current_session_prefers_latest_timestamp(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        older = _make_result(
            20_000_000,
            session_id="older",
            timestamp=datetime(2026, 3, 25, 9, 0, tzinfo=tzinfo),
        )
        newer = _make_result(
            8_000_000,
            session_id="newer",
            timestamp=datetime(2026, 3, 25, 11, 0, tzinfo=tzinfo),
        )
        report = build_report([older, newer], window=_make_window(), group_by=None, limit=5)

        self.assertEqual(report["current_session"]["session_id"], "newer")

    def test_session_detail_returns_single_session_summary(self) -> None:
        result = _make_result(12_000_000, session_id="focus-session")
        report = build_report([result], window=_make_window(), group_by=None, limit=5, session_id="focus-session")

        self.assertEqual(report["session_detail"]["session_id"], "focus-session")
        self.assertEqual(report["session_detail"]["events"], 1)

    def test_estimated_cost_is_reported_when_model_is_priced(self) -> None:
        report = build_report([_make_result(1_000_000, model="gpt-5.4")], window=_make_window(), group_by=None, limit=5)

        self.assertGreater(report["summary"]["estimated_cost_usd"], 0)
        self.assertEqual(report["summary"]["cost_accuracy"], "estimated")

    def test_missing_pricing_adds_diagnostic(self) -> None:
        report = build_report([_make_result(1_000_000, model="unknown-model")], window=_make_window(), group_by=None, limit=5)

        reasons = [item["reason"] for item in report["diagnostics"]]
        self.assertIn("estimated cost incomplete for one or more events", reasons)

    def test_trend_and_calendar_are_exposed(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        results = [
            _make_result(1_000_000 + index * 100_000, timestamp=datetime(2026, 3, 20 + index, 10, 0, tzinfo=tzinfo), session_id=f"s-{index}")
            for index in range(6)
        ]
        report = build_report(results, window=_make_window(days=7.0), group_by=None, limit=5, trend="7d", calendar="month", calendar_month="2026-03")

        self.assertEqual(report["charts"]["trend_7d"]["days"], 7)
        self.assertEqual(report["charts"]["calendar_month"]["month"], "2026-03")
        self.assertEqual(len(report["charts"]["calendar_month"]["days"]), 31)

    def test_plain_ascii_renderer_uses_ascii_graphics(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        results = [
            _make_result(2_000_000, timestamp=datetime(2026, 3, 24, 10, 0, tzinfo=tzinfo), session_id="a"),
            _make_result(4_000_000, timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo), session_id="b"),
        ]
        report = build_report(results, window=_make_window(days=2.0), group_by="day", limit=5, trend="7d", calendar="month", calendar_month="2026-03")
        rendered = render_report(report, plain_ascii=True, show_estimated_cost=True)

        self.assertIn("####", rendered)
        self.assertIn("最近 7 天", rendered)
        self.assertIn("Mo    Tu    We    Th    Fr    Sa    Su", rendered)
        self.assertIn("合计", rendered)
        self.assertIn("均值", rendered)
        self.assertIn("最高", rendered)
        self.assertNotIn("统计", rendered)

    def test_dashboard_mode_renders_trend_and_calendar_without_extra_flags(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        today_result = _make_result(
            4_000_000,
            timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo),
            session_id="today-session",
        )
        chart_results = [
            _make_result(
                1_000_000 + index * 500_000,
                timestamp=datetime(2026, 3, 19 + index, 10, 0, tzinfo=tzinfo),
                session_id=f"chart-{index}",
            )
            for index in range(7)
        ]
        report = build_report(
            [today_result],
            chart_results=chart_results,
            window=_make_window(),
            group_by=None,
            limit=5,
            dashboard_mode="today",
        )

        rendered = render_report(report, show_estimated_cost=True)
        self.assertIn("最近 7 天", rendered)
        self.assertIn("本月分布 2026-03", rendered)
        self.assertIn("按模型", rendered)
        self.assertIn("按项目", rendered)
        self.assertIn("去缓存后", rendered)
        self.assertIn("合计", rendered)
        self.assertGreaterEqual(
            sum(1 for line in rendered.splitlines() if "合计" in line and "估算 $" in line),
            2,
        )
        self.assertNotIn("诊断 / 缺失来源", rendered)

    def test_dashboard_mode_surfaces_missing_source_diagnostics(self) -> None:
        report = build_report(
            [_make_result(4_000_000), _make_unavailable_result()],
            window=_make_window(),
            group_by=None,
            limit=5,
            dashboard_mode="today",
        )

        rendered = render_report(report, show_estimated_cost=True)
        self.assertNotIn("诊断 / 缺失来源", rendered)
        self.assertNotIn("timing.json not found", rendered)

    def test_renderer_prefers_compact_token_units(self) -> None:
        report = build_report([_make_result(42_500_000)], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report, show_estimated_cost=True)

        self.assertIn("42.5M", rendered)
        self.assertNotIn("42,500,000", rendered)

    def test_renderer_shows_windows_project_basename(self) -> None:
        result = _make_result(3_000_000)
        original = result.events[0]
        result.events[0] = UsageEvent(
            source=original.source,
            provider=original.provider,
            timestamp=original.timestamp,
            session_id=original.session_id,
            project_path=r"C:\Users\boss\workspace\windows-demo",
            model=original.model,
            input_tokens=original.input_tokens,
            cached_input_tokens=original.cached_input_tokens,
            output_tokens=original.output_tokens,
            reasoning_tokens=original.reasoning_tokens,
            total_tokens=original.total_tokens,
            accuracy_level=original.accuracy_level,
            raw_event_kind=original.raw_event_kind,
            source_path=original.source_path,
            raw_model=original.raw_model,
            model_resolution=original.model_resolution,
            model_source=original.model_source,
        )
        report = build_report([result], window=_make_window(), group_by="project", limit=5)
        rendered = render_report(report, show_estimated_cost=True)

        self.assertIn("windows-demo", rendered)
        self.assertNotIn(r"C:\Users\boss\workspace\windows-demo", rendered)

    def test_trend_includes_zero_days_for_calendar_window(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        results = [
            _make_result(2_000_000, timestamp=datetime(2026, 3, 20, 10, 0, tzinfo=tzinfo), session_id="a"),
            _make_result(4_000_000, timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo), session_id="b"),
        ]
        report = build_report(results, window=_make_window(days=7.0), group_by=None, limit=5, trend="7d")

        points = report["charts"]["trend_7d"]["points"]
        self.assertEqual(len(points), 7)
        self.assertEqual(points[0]["date"], "2026-03-19")
        self.assertEqual(points[-1]["date"], "2026-03-25")
        self.assertEqual(report["charts"]["trend_7d"]["total_tokens"], 4_800_000)
        self.assertEqual(points[1]["total_tokens"], 2_000_000)
        self.assertEqual(points[1]["effective_tokens"], 1_600_000)
        self.assertEqual(points[2]["total_tokens"], 0)

    def test_trend_stats_use_total_average_and_peak(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        results = [
            _make_result(2_000_000, timestamp=datetime(2026, 3, 24, 10, 0, tzinfo=tzinfo), session_id="a"),
            _make_result(4_000_000, timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo), session_id="b"),
        ]
        report = build_report(results, window=_make_window(days=7.0), group_by=None, limit=5, trend="7d")
        rendered = render_report(report, show_estimated_cost=True)

        self.assertIn("03-24", rendered)
        self.assertIn("均值", rendered)
        self.assertIn("最高", rendered)
        self.assertIn("合计", rendered)
        self.assertNotIn("最低", rendered)
        self.assertNotIn("最新", rendered)
        self.assertNotIn("统计", rendered)

    def test_trend_and_calendar_total_stats_show_estimated_cost(self) -> None:
        tzinfo = ZoneInfo("US/Pacific")
        results = [
            _make_result(2_000_000, timestamp=datetime(2026, 3, 24, 10, 0, tzinfo=tzinfo), session_id="a"),
            _make_result(4_000_000, timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=tzinfo), session_id="b"),
        ]
        report = build_report(
            results,
            window=_make_window(days=7.0),
            group_by=None,
            limit=5,
            trend="7d",
            calendar="month",
            calendar_month="2026-03",
        )
        rendered = render_report(report, show_estimated_cost=True)

        self.assertGreaterEqual(
            sum(1 for line in rendered.splitlines() if "合计" in line and "估算 $" in line),
            2,
        )

    def test_diagnose_renderer_shows_detection_details(self) -> None:
        result = _make_unavailable_result(summary="Claude local-agent layout detected, but no token-bearing exact JSON was found")
        result.detection.details.extend(
            [
                "detected local-agent JSON layout markers: .claude.json, cowork_settings.json",
                "none of the JSON files under local-agent-mode-sessions expose both total_tokens and executor_end/grader_end",
            ]
        )

        rendered = render_diagnose(result, _make_window())

        self.assertIn("识别", rendered)
        self.assertIn(".claude.json", rendered)
        self.assertIn("executor_end/grader_end", rendered)


if __name__ == "__main__":
    unittest.main()
