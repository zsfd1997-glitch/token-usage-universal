from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SKILL_TEXT = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
ROUTING_TEXT = (REPO_ROOT / "references" / "skill-routing.md").read_text(encoding="utf-8")
OUTPUT_CONTRACT_TEXT = (
    REPO_ROOT / "references" / "skill-output-contract.md"
).read_text(encoding="utf-8")


def _skill_description() -> str:
    frontmatter_match = re.search(r"^---\n(.*?)\n---\n", SKILL_TEXT, re.DOTALL)
    if not frontmatter_match:
        raise AssertionError("SKILL.md 缺少 frontmatter")
    description_match = re.search(
        r'^description:\s*"(?P<value>.*)"$',
        frontmatter_match.group(1),
        re.MULTILINE,
    )
    if not description_match:
        raise AssertionError("SKILL.md frontmatter 缺少 description")
    return description_match.group("value")


class SkillContractTests(unittest.TestCase):
    def test_repo_skill_frontmatter_declares_trigger_and_non_trigger_cases(self) -> None:
        description = _skill_description()

        self.assertIn("Trigger when", description)
        self.assertIn("Do not trigger", description)
        self.assertIn("`token`, `用量`, `消耗量`, `使用量`, `消耗`", description)

    def test_repo_skill_uses_progressive_disclosure(self) -> None:
        self.assertIn("[skill-routing.md](references/skill-routing.md)", SKILL_TEXT)
        self.assertIn("[skill-output-contract.md](references/skill-output-contract.md)", SKILL_TEXT)
        self.assertIn("[source-contract.md](references/source-contract.md)", SKILL_TEXT)
        self.assertLessEqual(len(SKILL_TEXT.splitlines()), 80)

    def test_repo_skill_declares_short_trigger_phrases(self) -> None:
        self.assertIn("用户只说“token / 用量 / 消耗量 / 使用量 / 消耗”", ROUTING_TEXT)
        self.assertIn("- “token”", ROUTING_TEXT)
        self.assertIn("- “用量”", ROUTING_TEXT)
        self.assertIn("- “消耗量”", ROUTING_TEXT)
        self.assertIn("- “使用量”", ROUTING_TEXT)
        self.assertIn("- “消耗”", ROUTING_TEXT)

    def test_repo_skill_requires_ascii_hifi_panel_before_summary(self) -> None:
        self.assertIn(
            "这个 skill 的默认成品不是一句话摘要，而是一个带相关上下文的 `ascii-hifi` 面板。",
            OUTPUT_CONTRACT_TEXT,
        )
        self.assertIn(
            "只要底层 CLI 已返回 `ascii-hifi` 面板，最终回复必须先原样贴出面板，再补简短结论",
            OUTPUT_CONTRACT_TEXT,
        )
        self.assertIn("1. 先输出 `ascii-hifi` 面板", OUTPUT_CONTRACT_TEXT)
        self.assertIn("默认把面板放进 fenced code block", OUTPUT_CONTRACT_TEXT)
        self.assertIn(
            "不要把 ASCII 面板“翻译”为另一套表述后冒充等价输出",
            OUTPUT_CONTRACT_TEXT,
        )
        self.assertIn(
            "`费用` 默认按“去缓存后 token”估算，不把缓存 token 算进费用里",
            OUTPUT_CONTRACT_TEXT,
        )

    def test_readme_declares_repo_local_github_contract(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("GitHub 交付契约", readme_text)
        self.assertIn("以仓库根目录的 [SKILL.md]", readme_text)
        self.assertIn("不依赖 `~/.codex/skills/...` 里的本机覆盖文件", readme_text)
        self.assertIn("不依赖某台机器上的全局提示词或临时记忆", readme_text)
        self.assertIn("短触发词 `token / 用量 / 消耗量 / 使用量 / 消耗` 默认都视为“先看今天总览”", readme_text)
        self.assertIn("./references/skill-routing.md", readme_text)
        self.assertIn("./references/skill-output-contract.md", readme_text)


if __name__ == "__main__":
    unittest.main()
