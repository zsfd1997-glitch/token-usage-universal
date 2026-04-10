from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTING_TEXT = (REPO_ROOT / "references" / "skill-routing.md").read_text(encoding="utf-8")
OUTPUT_TEXT = (
    REPO_ROOT / "references" / "skill-output-contract.md"
).read_text(encoding="utf-8")


class SkillGuidanceContractTests(unittest.TestCase):
    def test_weekly_phrase_offers_short_choice(self) -> None:
        self.assertIn("最近一周 token 消耗情况", ROUTING_TEXT)
        self.assertIn("最近一个月 token 消耗情况", ROUTING_TEXT)
        self.assertIn("关闭", ROUTING_TEXT)

    def test_plain_text_downgrade_is_documented(self) -> None:
        self.assertIn("看不懂图", OUTPUT_TEXT)
        self.assertIn("纯文字版本", OUTPUT_TEXT)

    def test_exit_phrases_are_listed(self) -> None:
        for phrase in ["先这样", "够了", "不用继续", "先停", "先看到这里"]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, OUTPUT_TEXT)

    def test_default_panel_skeleton_is_fixed(self) -> None:
        for key in [
            "总 token",
            "去缓存后 token",
            "当前会话",
            "按模型",
            "按项目",
            "最近趋势",
            "月历热力图",
        ]:
            with self.subTest(key=key):
                self.assertIn(key, OUTPUT_TEXT)


if __name__ == "__main__":
    unittest.main()
