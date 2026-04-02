from __future__ import annotations

from pathlib import Path

from adapters.chromium_desktop import ChromiumDesktopAdapter, ChromiumDesktopSourceDefinition
from core.config import TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV


class ClaudeDesktopAdapter(ChromiumDesktopAdapter):
    def __init__(self, *, root: Path | None = None) -> None:
        super().__init__(
            ChromiumDesktopSourceDefinition(
                source_id="claude-desktop",
                display_name="Claude Desktop",
                provider="anthropic",
                env_name=TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV,
                app_names=("Claude",),
                response_url_keywords=(
                    "claude.ai/api/",
                    "api.anthropic.com/v1/",
                    "api.anthropic.com/mcp-registry/",
                ),
                usage_url_keywords=(
                    "claude.ai/api/organizations/",
                    "claude.ai/api/append_message",
                    "claude.ai/api/retry_message",
                    "api.anthropic.com/v1/messages",
                    "api.anthropic.com/v1/complete",
                ),
            ),
            root=root,
        )
        self.parser_version = "claude-desktop-v1"
