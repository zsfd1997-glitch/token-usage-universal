from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ascii_hifi import render_report
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


def _make_result(total_tokens: int, *, source: str = "codex", model: str = "gpt-5.4") -> SourceCollectResult:
    event = UsageEvent(
        source=source,
        provider="openai",
        timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("US/Pacific")),
        session_id=f"{source}-session-1",
        project_path="/tmp/example",
        model=model,
        input_tokens=total_tokens,
        cached_input_tokens=int(total_tokens * 0.2),
        output_tokens=0,
        reasoning_tokens=0,
        total_tokens=total_tokens,
        accuracy_level="exact",
        raw_event_kind="unit-test",
        source_path="/tmp/source.jsonl",
    )
    detection = SourceDetection(
        source_id=source,
        display_name=source,
        provider="openai",
        accuracy_level="exact",
        supported=True,
        available=True,
        summary="ready",
    )
    return SourceCollectResult(detection=detection, events=[event], scanned_files=1)


class ReportingTests(unittest.TestCase):
    def test_insights_include_latest_model_anchors(self) -> None:
        report = build_report([_make_result(12_000_000)], window=_make_window(), group_by=None, limit=5)
        insights = report["insights"]

        self.assertEqual(insights["model_anchor_openai"], "OpenAI GPT-5.3-Codex / GPT-5.4")
        self.assertEqual(insights["model_anchor_anthropic"], "Anthropic Opus 4.5 / Opus 4.6")
        self.assertEqual(insights["model_anchor_verified_at"], "2026-03-25")

    def test_ascii_report_uses_new_chinese_business_panel(self) -> None:
        report = build_report([_make_result(120_000_000)], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report)

        self.assertIn("GPT-5.3-Codex / GPT-5.4", rendered)
        self.assertIn("Opus 4.5 / Opus 4.6", rendered)
        self.assertIn("岗位对标", rendered)
        self.assertIn("团队场景", rendered)
        self.assertNotIn("HIFI Rank", rendered)
        self.assertNotIn("Codex 最新模型", rendered)
        self.assertNotIn("Claude 最新模型", rendered)

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

    def test_role_and_team_mapping(self) -> None:
        cases = [
            (5_000_000, "初级工程师 / 普通员工", "轻量、日常、基础辅助"),
            (20_000_000, "中级工程师", "稳定进入工程主流程"),
            (120_000_000, "资深工程师", "高强度个人生产"),
            (700_000_000, "Staff / Tech Lead", "多线程、高密度交付"),
            (2_500_000_000, "Principal / AI 平台负责人", "平台级、组织级火力"),
        ]
        for tokens, role, team in cases:
            with self.subTest(tokens=tokens):
                report = build_report([_make_result(tokens)], window=_make_window(), group_by=None, limit=5)
                insights = report["insights"]
                self.assertEqual(insights["role_anchor"], role)
                self.assertEqual(insights["team_anchor"], team)

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
                _make_result(8_000_000, source="generic-openai-compatible", model="deepseek-chat"),
            ],
            window=_make_window(),
            group_by="model",
            limit=5,
        )

        self.assertEqual(report["summary"]["models"], 2)
        self.assertEqual(report["by_model"][0]["name"], "gpt-5.4")
        self.assertEqual(report["by_model"][1]["name"], "deepseek-chat")

    def test_ascii_report_includes_by_model_section(self) -> None:
        report = build_report([_make_result(12_000_000, model="glm-4.5")], window=_make_window(), group_by="model", limit=5)
        rendered = render_report(report)

        self.assertIn("按模型", rendered)
        self.assertIn("glm-4.5", rendered)

    def test_ascii_report_explains_total_only_sources(self) -> None:
        result = _make_result(12_000_000, source="claude-code", model="claude-opus-4.6")
        event = result.events[0]
        total_only_event = UsageEvent(
            source=event.source,
            provider=event.provider,
            timestamp=event.timestamp,
            session_id=event.session_id,
            project_path=event.project_path,
            model=event.model,
            input_tokens=None,
            cached_input_tokens=None,
            output_tokens=None,
            reasoning_tokens=None,
            total_tokens=event.total_tokens,
            accuracy_level=event.accuracy_level,
            raw_event_kind=event.raw_event_kind,
            source_path=event.source_path,
        )
        result.events = [total_only_event]

        report = build_report([result], window=_make_window(), group_by=None, limit=5)
        rendered = render_report(report)

        self.assertIn("只提供 total_tokens", rendered)


if __name__ == "__main__":
    unittest.main()
