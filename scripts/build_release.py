#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
ROOT_LEVEL_EXPORT_IGNORES = {
    ".claude",
    ".git",
    ".superchain",
    ".knowledge-superchain",
    ".DS_Store",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "AGENTS_CHANGELOG.md",
    "GITEE_UPLOAD.md",
    "_archive",
    "build",
    "dist",
    "findings.md",
    "master-plan.md",
    "master-report.md",
    "progress.md",
    "superchain_observability.config.json",
    "task_plan.md",
    "输出",
}
NESTED_EXPORT_IGNORES = {
    Path("examples") / "vm-testing": {"output"},
}

# --skill-only distribution mode. Follows the 先锋组织 artifact convention:
# KEEPS README.md (先锋 7-section template with team/type/name/contributor/
# created/version/status/tags/usage_count/effect frontmatter) and LICENSE
# at the top level — these are required 先锋 artifacts, NOT auxiliary files.
# DROPS only: CHANGELOG/CoC/CONTRIBUTING/SECURITY/SUPPORT/docs/.github/
# examples/tests/build-tooling/fixtures — these are governance / repo-
# tooling / dev-harness artifacts that end users don't need.
SKILL_ONLY_ROOT_IGNORES = {
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs",
    ".github",
    ".gitignore",
    "examples",
}
SKILL_ONLY_SCRIPT_IGNORES_PREFIXES = ("test_", "build_")
SKILL_ONLY_SCRIPT_IGNORES_EXACT = {"fixtures"}


def _make_ignore(skill_only: bool):
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        current_dir = Path(directory).resolve()
        try:
            relative_dir = current_dir.relative_to(SKILL_ROOT.resolve())
        except ValueError:
            relative_dir = Path(".")

        for name in names:
            if name in ROOT_LEVEL_EXPORT_IGNORES and relative_dir == Path("."):
                ignored.add(name)
            if name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store", ".coverage", ".venv", "build", "dist"}:
                ignored.add(name)
            if name.endswith(".pyc"):
                ignored.add(name)

        if skill_only:
            if relative_dir == Path("."):
                ignored.update(set(names) & SKILL_ONLY_ROOT_IGNORES)
            if relative_dir == Path("scripts"):
                for name in names:
                    if name in SKILL_ONLY_SCRIPT_IGNORES_EXACT:
                        ignored.add(name)
                    elif name.startswith(SKILL_ONLY_SCRIPT_IGNORES_PREFIXES) and name.endswith(".py"):
                        ignored.add(name)

        nested_ignores = NESTED_EXPORT_IGNORES.get(relative_dir)
        if nested_ignores:
            ignored.update(set(names) & nested_ignores)
        return ignored

    return _ignore


# Backward-compat shim for tests / callers that invoke the default ignore
# filter directly (pre-skill-only refactor). Keep the same signature.
_ignore = _make_ignore(skill_only=False)


def export_release(output_dir: Path, *, force: bool, skill_only: bool = False) -> Path:
    if output_dir.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_ROOT, output_dir, ignore=_make_ignore(skill_only))
    return output_dir


def create_zip_from_directory(source_dir: Path, zip_path: Path, *, root_name: str | None = None, force: bool) -> Path:
    if zip_path.exists():
        if not force:
            raise FileExistsError(f"zip file already exists: {zip_path}")
        zip_path.unlink()

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    archive_root = Path(root_name or source_dir.name)
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file():
                continue
            archive_name = archive_root / file_path.relative_to(source_dir)
            archive.write(file_path, archive_name.as_posix())
    return zip_path


def run_release_validation() -> None:
    unittest_command = [sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-t", ".", "-p", "test_*.py"]
    subprocess.run(unittest_command, cwd=SKILL_ROOT, check=True)

    gate_command = [sys.executable, "scripts/token_usage.py", "release-gate", "--format", "json"]
    gate_result = subprocess.run(gate_command, cwd=SKILL_ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(gate_result.stdout)
    if payload["summary"]["status"] != "pass":
        raise RuntimeError("release-gate failed; inspect `python3 scripts/token_usage.py release-gate` for details")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a release directory for token-usage-universal")
    parser.add_argument("--output-dir", required=True, help="target directory for the exported release")
    parser.add_argument("--force", action="store_true", help="overwrite the target directory if it already exists")
    parser.add_argument("--validate", action="store_true", help="run unit tests and release-gate before exporting")
    parser.add_argument("--zip-path", help="optional standard ZIP output path for Windows-friendly distribution")
    parser.add_argument("--zip-root-name", help="optional top-level folder name inside the ZIP archive")
    parser.add_argument(
        "--skill-only",
        action="store_true",
        help="produce a minimal skill-package per skill-creator rules: drops README/CHANGELOG/docs/.github/examples/tests/build-tooling; keeps only SKILL.md + LICENSE + runtime scripts + references",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir).expanduser()
    if args.validate:
        run_release_validation()
    export_release(output_dir, force=args.force, skill_only=args.skill_only)
    if args.zip_path:
        zip_path = Path(args.zip_path).expanduser()
        create_zip_from_directory(
            output_dir,
            zip_path,
            root_name=args.zip_root_name,
            force=args.force,
        )
    print(output_dir)
    if args.zip_path:
        print(Path(args.zip_path).expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
