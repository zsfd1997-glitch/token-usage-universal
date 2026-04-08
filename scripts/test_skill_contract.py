from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class SkillContractTests(unittest.TestCase):
    def test_repo_skill_declares_short_trigger_phrases(self) -> None:
        skill_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("用户只说“token / 用量 / 消耗量 / 使用量 / 消耗”", skill_text)
        self.assertIn("- “token”", skill_text)
        self.assertIn("- “用量”", skill_text)
        self.assertIn("- “消耗量”", skill_text)
        self.assertIn("- “使用量”", skill_text)
        self.assertIn("- “消耗”", skill_text)

    def test_repo_skill_requires_ascii_hifi_panel_before_summary(self) -> None:
        skill_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("这个 skill 的默认成品不是一句话摘要，而是一个带相关上下文的 `ascii-hifi` 面板。", skill_text)
        self.assertIn("只要底层 CLI 已返回 `ascii-hifi` 面板，最终回复必须先原样贴出面板，再补简短结论", skill_text)
        self.assertIn("1. 先输出 `ascii-hifi` 面板", skill_text)

    def test_readme_declares_repo_local_github_contract(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("GitHub 交付契约", readme_text)
        self.assertIn("以仓库根目录的 [SKILL.md]", readme_text)
        self.assertIn("不依赖 `~/.codex/skills/...` 里的本机覆盖文件", readme_text)
        self.assertIn("不依赖某台机器上的全局提示词或临时记忆", readme_text)
        self.assertIn("短触发词 `token / 用量 / 消耗量 / 使用量 / 消耗` 默认都视为“先看今天总览”", readme_text)


if __name__ == "__main__":
    unittest.main()
