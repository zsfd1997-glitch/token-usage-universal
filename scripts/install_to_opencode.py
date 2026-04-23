#!/usr/bin/env python3
"""One-command installer: make token-usage-universal discoverable by OpenCode CLI.

OpenCode CLI loads skills from its config skills/ directory. This script
links the repo into that directory so the next `opencode` invocation can
pick up our SKILL.md without any hand-rolled config.

Usage:
    python3 scripts/install_to_opencode.py              # install (symlink)
    python3 scripts/install_to_opencode.py --dry-run    # print plan, do nothing
    python3 scripts/install_to_opencode.py --uninstall  # remove the link
    python3 scripts/install_to_opencode.py --target DIR # override skills dir

Exit codes:
    0   success (installed / already-installed / uninstalled)
    1   failure (target not writable, symlink not supported, etc.)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAME = "token-usage-universal"


def _candidate_skills_dirs() -> list[Path]:
    """Where could OpenCode CLI be looking for skills on this host?

    OpenCode stores config under the XDG-style config dir. On macOS/Linux
    this is $XDG_CONFIG_HOME or ~/.config; on Windows OpenCode follows the
    same layout (~/.config on recent builds; some older/alt builds may use
    %APPDATA%\\opencode). Return all plausible candidates, the caller picks
    the first existing one (or the first writable one).
    """
    candidates: list[Path] = []
    home = Path.home()

    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        candidates.append(Path(xdg) / "opencode" / "skills")

    candidates.append(home / ".config" / "opencode" / "skills")

    if os.name == "nt":
        for env_name in ("APPDATA", "LOCALAPPDATA"):
            base = os.environ.get(env_name, "").strip()
            if base:
                candidates.append(Path(base) / "opencode" / "skills")

    # De-dup preserving order.
    seen: set[str] = set()
    uniq: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(candidate)
    return uniq


def _resolve_repo_root() -> Path:
    """Absolute path to the repo root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def _pick_target_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for candidate in _candidate_skills_dirs():
        if candidate.exists():
            return candidate
    # None exist yet — use the first candidate and create on install.
    candidates = _candidate_skills_dirs()
    if not candidates:
        raise SystemExit("no candidate OpenCode skills directory found on this host")
    return candidates[0]


def _link_or_copy(source: Path, link_path: Path) -> str:
    """Create link_path pointing at source. Returns method used for reporting.

    Priority:
      1. symlink (works on macOS / Linux / Windows with Developer Mode)
      2. Windows directory junction via `mklink /J` (no admin needed on NTFS)
      3. full copy (always works, but diverges from repo after updates)
    """
    try:
        link_path.symlink_to(source, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        pass

    if os.name == "nt":
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(source)],
                check=True,
                capture_output=True,
            )
            return "junction"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    shutil.copytree(source, link_path, symlinks=False)
    return "copy"


def _current_link_target(link_path: Path) -> str | None:
    if link_path.is_symlink():
        try:
            return os.readlink(link_path)
        except OSError:
            return None
    if link_path.is_dir():
        return "(copy or junction)"
    return None


def _remove(link_path: Path) -> None:
    if link_path.is_symlink() or link_path.is_file():
        link_path.unlink()
    elif link_path.is_dir():
        shutil.rmtree(link_path)


def install(*, target_dir: Path, dry_run: bool) -> int:
    repo = _resolve_repo_root()
    skill_md = repo / "SKILL.md"
    if not skill_md.is_file():
        print(f"error: SKILL.md not found at {skill_md}", file=sys.stderr)
        return 1

    link_path = target_dir / SKILL_NAME
    existing = _current_link_target(link_path)

    print(f"repo:    {repo}")
    print(f"target:  {target_dir}")
    print(f"link:    {link_path}")
    if existing == str(repo):
        print("status:  already installed and pointing at this repo. Nothing to do.")
        return 0
    if existing:
        print(f"status:  existing link -> {existing}  (will replace)")
    else:
        print("status:  will create new link")

    if dry_run:
        print("\n(dry-run) no changes made.")
        return 0

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"created: {target_dir}")

    if existing:
        _remove(link_path)

    method = _link_or_copy(repo, link_path)

    # Sanity check: post-install SKILL.md must be reachable.
    if not (link_path / "SKILL.md").is_file():
        print(f"error: post-install SKILL.md not readable at {link_path}", file=sys.stderr)
        return 1

    print(f"\ninstalled via {method}.")
    print("next steps:")
    print("  1. restart / re-launch opencode CLI (it scans skills on startup)")
    print("  2. in an opencode conversation, say:  token")
    print("     or:  帮我看今天 token 用量")
    print("  the agent will run scripts/token_usage.py report --today automatically.")
    if method == "copy":
        print(
            "\nnote: symlink was not available on this host, so files were COPIED. "
            "Future updates to the repo will NOT automatically propagate — rerun "
            "this installer after `git pull`."
        )
    return 0


def uninstall(*, target_dir: Path, dry_run: bool) -> int:
    link_path = target_dir / SKILL_NAME
    if not link_path.exists() and not link_path.is_symlink():
        print(f"nothing to uninstall: {link_path} does not exist.")
        return 0

    existing = _current_link_target(link_path)
    print(f"target:  {link_path}  ({existing or 'unknown'})")
    if dry_run:
        print("(dry-run) would remove.")
        return 0

    _remove(link_path)
    print(f"removed: {link_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan without changing anything")
    parser.add_argument("--uninstall", action="store_true", help="remove the skill from OpenCode's skills dir")
    parser.add_argument("--target", help="override the OpenCode skills directory (advanced)")
    args = parser.parse_args()

    try:
        target = _pick_target_dir(args.target)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.uninstall:
        return uninstall(target_dir=target, dry_run=args.dry_run)
    return install(target_dir=target, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
