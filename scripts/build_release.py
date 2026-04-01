#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in {
            "__pycache__",
            ".pytest_cache",
            ".DS_Store",
            ".git",
            ".superchain",
            "输出",
            "task_plan.md",
            "progress.md",
            "findings.md",
            "master-plan.md",
            "master-report.md",
            "superchain_observability.config.json",
        }:
            ignored.add(name)
        if name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def export_release(output_dir: Path, *, force: bool) -> Path:
    if output_dir.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_ROOT, output_dir, ignore=_ignore)
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a GitHub-ready release directory for token-usage-universal")
    parser.add_argument("--output-dir", required=True, help="target directory for the exported release")
    parser.add_argument("--force", action="store_true", help="overwrite the target directory if it already exists")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).expanduser()
    export_release(output_dir, force=args.force)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
