from __future__ import annotations

import os
from pathlib import Path


TOKEN_USAGE_CODEX_ROOT_ENV = "TOKEN_USAGE_CODEX_ROOT"
TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT"
TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT"
TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV = "TOKEN_USAGE_GENERIC_LOG_GLOBS"


def _path_text(path: Path) -> str:
    return str(path.expanduser())


ENVIRONMENT_VARIABLES = (
    {
        "name": TOKEN_USAGE_CODEX_ROOT_ENV,
        "description": "Override the Codex session root directory.",
        "default": lambda: _path_text(Path.home() / ".codex" / "sessions"),
    },
    {
        "name": TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
        "description": "Override the Claude transcript directory.",
        "default": lambda: _path_text(Path.home() / ".claude" / "transcripts"),
    },
    {
        "name": TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
        "description": "Override the Claude local-agent-mode-sessions directory.",
        "default": lambda: _path_text(
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "local-agent-mode-sessions"
        ),
    },
    {
        "name": TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
        "description": "Comma-separated JSON/JSONL glob patterns for generic exact logs.",
        "default": lambda: "",
    },
)


def resolve_path_override(env_name: str, default_path: Path) -> Path:
    raw_value = os.environ.get(env_name, "").strip()
    if not raw_value:
        return default_path
    return Path(os.path.expanduser(raw_value))


def environment_variable_statuses() -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for item in ENVIRONMENT_VARIABLES:
        default_value = item["default"]()
        configured_value = os.environ.get(item["name"], "").strip()
        statuses.append(
            {
                "name": item["name"],
                "description": item["description"],
                "configured": bool(configured_value),
                "value": configured_value or None,
                "default": default_value or None,
            }
        )
    return statuses
