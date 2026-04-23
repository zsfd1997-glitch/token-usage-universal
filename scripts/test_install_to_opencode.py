from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from install_to_opencode import (  # noqa: E402
    SKILL_NAME,
    _candidate_skills_dirs,
    _current_link_target,
    _link_or_copy,
    _pick_target_dir,
    install,
    uninstall,
)


class CandidateDirsTests(unittest.TestCase):
    def test_xdg_config_home_wins_when_set(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/alt/xdg"}, clear=False):
            candidates = _candidate_skills_dirs()
        self.assertEqual(candidates[0], Path("/alt/xdg") / "opencode" / "skills")

    def test_default_mac_linux_path_always_present(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}, clear=False):
            candidates = _candidate_skills_dirs()
        home_default = Path.home() / ".config" / "opencode" / "skills"
        self.assertIn(home_default, candidates)


class InstallFlowTests(unittest.TestCase):
    def test_install_creates_symlink_to_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "opencode-skills"
            exit_code = install(target_dir=target, dry_run=False)
            link = target / SKILL_NAME
            self.assertEqual(exit_code, 0)
            self.assertTrue(link.exists())
            self.assertTrue((link / "SKILL.md").is_file())

    def test_install_dry_run_does_not_touch_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "dry-run-skills"
            exit_code = install(target_dir=target, dry_run=True)
            self.assertEqual(exit_code, 0)
            self.assertFalse(target.exists())

    def test_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "opencode-skills"
            first = install(target_dir=target, dry_run=False)
            second = install(target_dir=target, dry_run=False)
            self.assertEqual(first, 0)
            self.assertEqual(second, 0)

    def test_uninstall_removes_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "opencode-skills"
            install(target_dir=target, dry_run=False)
            link = target / SKILL_NAME
            self.assertTrue(link.exists())
            exit_code = uninstall(target_dir=target, dry_run=False)
            self.assertEqual(exit_code, 0)
            self.assertFalse(link.exists())

    def test_uninstall_is_noop_when_not_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "opencode-skills"
            target.mkdir()
            exit_code = uninstall(target_dir=target, dry_run=False)
            self.assertEqual(exit_code, 0)


class LinkOrCopyFallbackTests(unittest.TestCase):
    def test_falls_back_to_copy_when_symlink_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n")
            link = Path(tmp) / "link"

            # Simulate no-symlink host: symlink_to raises OSError. We also
            # force os.name == "posix" so the junction branch is skipped.
            with patch("install_to_opencode.Path.symlink_to", side_effect=OSError("denied")), \
                 patch.object(sys.modules["install_to_opencode"].os, "name", "posix"):
                method = _link_or_copy(source, link)
            self.assertEqual(method, "copy")
            self.assertTrue((link / "SKILL.md").is_file())


class PickTargetDirTests(unittest.TestCase):
    def test_explicit_target_overrides_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _pick_target_dir(tmp)
        self.assertEqual(result, Path(tmp).resolve())


if __name__ == "__main__":
    unittest.main()
