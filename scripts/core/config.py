from __future__ import annotations

import os
import re
import sys
from pathlib import Path


TOKEN_USAGE_CODEX_ROOT_ENV = "TOKEN_USAGE_CODEX_ROOT"
TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT"
TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV = "TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT"
TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV = "TOKEN_USAGE_CLAUDE_DESKTOP_ROOT"
TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV = "TOKEN_USAGE_MINIMAX_AGENT_ROOT"
TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV = "TOKEN_USAGE_KIMI_DESKTOP_ROOT"
TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV = "TOKEN_USAGE_GLM_DESKTOP_ROOT"
TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV = "TOKEN_USAGE_QWEN_DESKTOP_ROOT"
TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV = "TOKEN_USAGE_DOUBAO_DESKTOP_ROOT"
TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV = "TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT"
TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT_ENV = "TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT"
TOKEN_USAGE_QIANFAN_DESKTOP_ROOT_ENV = "TOKEN_USAGE_QIANFAN_DESKTOP_ROOT"
TOKEN_USAGE_YUANBAO_DESKTOP_ROOT_ENV = "TOKEN_USAGE_YUANBAO_DESKTOP_ROOT"
TOKEN_USAGE_QWEN_CODE_ROOT_ENV = "TOKEN_USAGE_QWEN_CODE_ROOT"
TOKEN_USAGE_KIMI_CLI_ROOT_ENV = "TOKEN_USAGE_KIMI_CLI_ROOT"
TOKEN_USAGE_OPENCODE_BIN_ENV = "TOKEN_USAGE_OPENCODE_BIN"
TOKEN_USAGE_OPENCODE_ROOTS_ENV = "TOKEN_USAGE_OPENCODE_ROOTS"
TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV = "TOKEN_USAGE_GENERIC_LOG_GLOBS"
TOKEN_USAGE_DISCOVERY_ROOTS_ENV = "TOKEN_USAGE_DISCOVERY_ROOTS"
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


def default_minimax_agent_root(
    *,
    os_name: str | None = None,
    home: Path | None = None,
    appdata: str | None = None,
    platform_name: str | None = None,
) -> Path:
    target_os = os_name or os.name
    home_path = home or Path.home()
    if target_os == "nt":
        appdata_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        base = Path(appdata_text) if appdata_text else home_path / "AppData" / "Roaming"
        return base / "MiniMax Agent"
    if (platform_name or sys.platform) == "darwin":
        return home_path / "Library" / "Application Support" / "MiniMax Agent"
    return home_path / ".config" / "MiniMax Agent"


def default_desktop_app_roots(
    app_names: tuple[str, ...],
    *,
    os_name: str | None = None,
    home: Path | None = None,
    appdata: str | None = None,
    localappdata: str | None = None,
    platform_name: str | None = None,
) -> list[Path]:
    target_os = os_name or os.name
    home_path = home or Path.home()
    names = tuple(dict.fromkeys(name for name in app_names if name))
    if not names:
        return []

    roots: list[Path] = []
    if target_os == "nt":
        roaming_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        local_text = (localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA", "")).strip()
        roaming_base = Path(roaming_text) if roaming_text else home_path / "AppData" / "Roaming"
        local_base = Path(local_text) if local_text else home_path / "AppData" / "Local"
        for name in names:
            roots.append(roaming_base / name)
            roots.append(local_base / name)
        return roots

    if (platform_name or sys.platform) == "darwin":
        for name in names:
            roots.append(home_path / "Library" / "Application Support" / name)
        return roots

    for name in names:
        roots.append(home_path / ".config" / name)
        roots.append(home_path / ".local" / "share" / name)
    return roots


def default_opencode_roots(
    *,
    os_name: str | None = None,
    home: Path | None = None,
    appdata: str | None = None,
    localappdata: str | None = None,
    platform_name: str | None = None,
) -> list[Path]:
    target_os = os_name or os.name
    home_path = home or Path.home()
    if target_os == "nt":
        roots: list[Path] = []
        roaming_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        local_text = (localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA", "")).strip()
        for base_text in (roaming_text, local_text):
            if not base_text:
                continue
            base = Path(base_text)
            roots.extend(
                [
                    base / "OpenCode",
                    base / "ai.opencode.desktop",
                    base / "opencode",
                ]
            )
        if roots:
            return roots
        return [
            home_path / "AppData" / "Roaming" / "OpenCode",
            home_path / "AppData" / "Roaming" / "ai.opencode.desktop",
            home_path / "AppData" / "Local" / "opencode",
        ]
    roots = [
        home_path / ".config" / "opencode",
        home_path / ".local" / "state" / "opencode",
        home_path / ".local" / "share" / "opencode",
        home_path / ".opencode",
    ]
    if (platform_name or sys.platform) == "darwin":
        roots.extend(
            [
                home_path / "Library" / "Application Support" / "OpenCode",
                home_path / "Library" / "Application Support" / "ai.opencode.desktop",
            ]
        )
    return roots


def default_cache_root(
    *,
    os_name: str | None = None,
    home: Path | None = None,
    localappdata: str | None = None,
    appdata: str | None = None,
    platform_name: str | None = None,
) -> Path:
    target_os = os_name or os.name
    home_path = home or Path.home()
    if target_os == "nt":
        local_text = (localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA", "")).strip()
        roaming_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        base = Path(local_text or roaming_text) if (local_text or roaming_text) else home_path / "AppData" / "Local"
        return base / "token-usage-universal" / "cache"
    if (platform_name or sys.platform) == "darwin":
        return home_path / "Library" / "Caches" / "token-usage-universal"
    return home_path / ".cache" / "token-usage-universal"


def default_qwen_runtime_root(*, home: Path | None = None) -> Path:
    home_path = home or Path.home()
    configured = os.environ.get("QWEN_RUNTIME_DIR", "").strip()
    if configured:
        return Path(expand_path_text(configured))
    return home_path / ".qwen"


def default_kimi_share_root(*, home: Path | None = None) -> Path:
    home_path = home or Path.home()
    configured = os.environ.get("KIMI_SHARE_DIR", "").strip()
    if configured:
        return Path(expand_path_text(configured))
    return home_path / ".kimi"


def default_discovery_roots(
    *,
    os_name: str | None = None,
    home: Path | None = None,
    appdata: str | None = None,
    localappdata: str | None = None,
) -> list[Path]:
    target_os = os_name or os.name
    home_path = home or Path.home()
    if target_os == "nt":
        roots: list[Path] = []
        local_text = (localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA", "")).strip()
        roaming_text = (appdata if appdata is not None else os.environ.get("APPDATA", "")).strip()
        if local_text:
            roots.append(Path(local_text))
        if roaming_text:
            roots.append(Path(roaming_text))
        if not roots:
            roots.extend(
                [
                    home_path / "AppData" / "Local",
                    home_path / "AppData" / "Roaming",
                ]
            )
        return roots
    roots = [
        home_path / ".config",
        home_path / ".local" / "state",
        home_path / ".local" / "share",
    ]
    if sys.platform == "darwin":
        roots.append(home_path / "Library" / "Application Support")
    return roots


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
        "name": TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV,
        "description": "Override the Claude Desktop app-data directory.",
        "default": lambda: ",".join(_path_text(path) for path in default_desktop_app_roots(("Claude",))),
    },
    {
        "name": TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV,
        "description": "Override the MiniMax Agent desktop data directory.",
        "default": lambda: _path_text(default_minimax_agent_root()),
    },
    {
        "name": TOKEN_USAGE_KIMI_DESKTOP_ROOT_ENV,
        "description": "Override the Kimi Desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("Kimi", "Moonshot", "Moonshot AI"))
        ),
    },
    {
        "name": TOKEN_USAGE_GLM_DESKTOP_ROOT_ENV,
        "description": "Override the GLM Desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("GLM", "Z.ai", "Zhipu AI", "BigModel", "Z Code", "ZCODE"))
        ),
    },
    {
        "name": TOKEN_USAGE_QWEN_DESKTOP_ROOT_ENV,
        "description": "Override the Qwen / DashScope desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("Qwen", "DashScope", "Tongyi"))
        ),
    },
    {
        "name": TOKEN_USAGE_DOUBAO_DESKTOP_ROOT_ENV,
        "description": "Override the Doubao desktop app-data directory.",
        "default": lambda: ",".join(_path_text(path) for path in default_desktop_app_roots(("Doubao", "豆包"))),
    },
    {
        "name": TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT_ENV,
        "description": "Override the Perplexity desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("Perplexity", "Perplexity Desktop", "Comet"))
        ),
    },
    {
        "name": TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT_ENV,
        "description": "Override the DeepSeek desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("DeepSeek", "DeepSeek App"))
        ),
    },
    {
        "name": TOKEN_USAGE_QIANFAN_DESKTOP_ROOT_ENV,
        "description": "Override the Baidu Qianfan / Wenxin desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("Qianfan", "Wenxin", "Wenxiaoyan", "文小言", "文心"))
        ),
    },
    {
        "name": TOKEN_USAGE_YUANBAO_DESKTOP_ROOT_ENV,
        "description": "Override the Tencent Yuanbao desktop app-data directory.",
        "default": lambda: ",".join(
            _path_text(path) for path in default_desktop_app_roots(("Yuanbao", "Tencent Yuanbao", "元宝", "腾讯元宝"))
        ),
    },
    {
        "name": TOKEN_USAGE_QWEN_CODE_ROOT_ENV,
        "description": "Override the Qwen Code CLI runtime root (~/.qwen or QWEN_RUNTIME_DIR).",
        "default": lambda: _path_text(default_qwen_runtime_root()),
    },
    {
        "name": TOKEN_USAGE_KIMI_CLI_ROOT_ENV,
        "description": "Override the Kimi CLI share root (~/.kimi or KIMI_SHARE_DIR).",
        "default": lambda: _path_text(default_kimi_share_root()),
    },
    {
        "name": TOKEN_USAGE_OPENCODE_BIN_ENV,
        "description": "Override the OpenCode CLI executable used for session export and stats.",
        "default": lambda: "opencode",
    },
    {
        "name": TOKEN_USAGE_OPENCODE_ROOTS_ENV,
        "description": "Comma-separated OpenCode roots to scan for local logs, storage, and desktop state.",
        "default": lambda: ",".join(_path_text(path) for path in default_opencode_roots()),
    },
    {
        "name": TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
        "description": "Comma-separated JSON/JSONL glob patterns for OpenAI/Anthropic-compatible exact usage logs.",
        "default": lambda: "",
    },
    {
        "name": TOKEN_USAGE_DISCOVERY_ROOTS_ENV,
        "description": "Comma-separated roots for auto-discovering generic API usage logs when they do not live in standard locations.",
        "default": lambda: ",".join(_path_text(path) for path in default_discovery_roots()),
    },
    {
        "name": TOKEN_USAGE_CACHE_ROOT_ENV,
        "description": "Override the token-usage-universal incremental cache directory.",
        "default": lambda: _path_text(default_cache_root()),
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
