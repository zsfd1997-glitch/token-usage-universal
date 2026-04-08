from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


class GitHubRepoContractTests(unittest.TestCase):
    def test_community_health_files_exist(self) -> None:
        expected_paths = [
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "LICENSE",
            "README.md",
            "SECURITY.md",
            "SUPPORT.md",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/config.yml",
        ]

        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), relative_path)

    def test_readme_declares_github_distribution_contract(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("GitHub 交付契约", readme_text)
        self.assertIn("不依赖 `~/.codex/skills/...` 里的本机覆盖文件", readme_text)
        self.assertIn("不依赖某台机器上的全局提示词或临时记忆", readme_text)

    def test_security_and_support_documents_cover_expected_paths(self) -> None:
        security_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
        support_text = (REPO_ROOT / "SUPPORT.md").read_text(encoding="utf-8")

        self.assertIn("Please do not open a public GitHub issue", security_text)
        self.assertIn("security@zsfd.dev", security_text)
        self.assertIn("Use the following channels based on the kind of help you need", support_text)
        self.assertIn("SECURITY.md", support_text)


if __name__ == "__main__":
    unittest.main()
