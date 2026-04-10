from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_release


class BuildReleaseTests(unittest.TestCase):
    def test_ignore_filters_root_level_local_workfiles(self) -> None:
        ignored = build_release._ignore(
            str(build_release.SKILL_ROOT),
            [
                ".claude",
                ".superchain",
                "AGENTS_CHANGELOG.md",
                "GITEE_UPLOAD.md",
                "findings.md",
                "README.md",
            ],
        )

        self.assertIn(".claude", ignored)
        self.assertIn(".superchain", ignored)
        self.assertIn("AGENTS_CHANGELOG.md", ignored)
        self.assertIn("GITEE_UPLOAD.md", ignored)
        self.assertIn("findings.md", ignored)
        self.assertNotIn("README.md", ignored)

    def test_ignore_filters_hosted_evidence_output_only_in_vm_testing(self) -> None:
        vm_testing_dir = build_release.SKILL_ROOT / "examples" / "vm-testing"
        ignored = build_release._ignore(str(vm_testing_dir), ["output", "README.md"])

        self.assertIn("output", ignored)
        self.assertNotIn("README.md", ignored)

    def test_create_zip_from_directory_produces_windows_friendly_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "release"
            (source_dir / "docs").mkdir(parents=True)
            (source_dir / "README.md").write_text("hello\n", encoding="utf-8")
            (source_dir / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")

            zip_path = Path(tmpdir) / "token-usage-universal.zip"
            build_release.create_zip_from_directory(
                source_dir,
                zip_path,
                root_name="token-usage-universal",
                force=False,
            )

            with ZipFile(zip_path) as archive:
                names = set(archive.namelist())

            self.assertIn("token-usage-universal/README.md", names)
            self.assertIn("token-usage-universal/docs/guide.md", names)
            self.assertTrue(all("\\" not in name for name in names))

    def test_exported_markdown_does_not_use_local_absolute_paths(self) -> None:
        shipped_markdown_files = [
            build_release.SKILL_ROOT / "SUPPORT.md",
            build_release.SKILL_ROOT / "CODE_OF_CONDUCT.md",
            build_release.SKILL_ROOT / "docs" / "PUBLISH.md",
            build_release.SKILL_ROOT / "docs" / "SIMULATED_MACHINE_TESTING.md",
            build_release.SKILL_ROOT / "docs" / "VM_RUNBOOK.md",
            build_release.SKILL_ROOT / "examples" / "vm-testing" / "README.md",
        ]

        for markdown_file in shipped_markdown_files:
            with self.subTest(path=markdown_file):
                text = markdown_file.read_text(encoding="utf-8")
                self.assertNotIn("](/Users/", text)


if __name__ == "__main__":
    unittest.main()
