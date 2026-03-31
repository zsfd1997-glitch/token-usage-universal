from __future__ import annotations

import os
import re
from pathlib import Path


TOKEN_USAGE_CODEX_ROOT_ENV = "TOKEN_USAGE_CODEX_ROOT"
TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT"
TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT"
TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV = "TOKEN_USAGE_GENERIC_LOG_GLOBS"
TOKEN_USAGE_CACHE_ROOT_ENV = "TOKEN_USAGE_CACHE_ROOT"
_WINDOWS_ENV_RE = re.compile(r"%([^%]+)%")


def _path_text(path: Path) -> str:
    return str(path.expanduser())


def expand_path_text(raw_value: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(raw_value))
    return _WINDOWS_ENV_RE.sub(lambda match: os.environ.get(match.group(1), match.group(0)), expanded)


def default_claude_local_agent_root(
    *,
    os_name: str | None = None,
    home: Path | None = None,
    appdata: str | None = None,
) -> Path:
    target_os = os_name or os.name
    home_path = home or Path.home()
    if target_os == "nt":
        appdata_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        base = Path(appdata_text) if appdata_text else home_path / "AppData" / "Roaming"
        return base / "Claude" / "local-agent-mode-sessions"
    return (
        home_path
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
    )


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
        "default": lambda: _path_text(default_claude_local_agent_root()),
    },
    {
        "name": TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
        "description": "Comma-separated JSON/JSONL glob patterns for generic exact logs.",
        "default": lambda: "",
    },
    {
        "name": TOKEN_USAGE_CACHE_ROOT_ENV,
        "description": "Override the token-usage-universal incremental cache directory.",
        "default": lambda: _path_text(Path.home() / ".codex" / "cache" / "token-usage-universal"),
    },
)


def resolve_path_override(env_name: str, default_path: Path) -> Path:
    raw_value = os.environ.get(env_name, "").strip()
    if not raw_value:
        return default_path
    return Path(expand_path_text(raw_value))


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
