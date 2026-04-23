from __future__ import annotations

from pathlib import Path

from adapters.chromium_desktop import ChromiumDesktopAdapter, ChromiumDesktopSourceDefinition
from core.config import TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV, default_minimax_agent_root, resolve_path_override


class MiniMaxAgentAdapter(ChromiumDesktopAdapter):
    def __init__(self, *, root: Path | None = None) -> None:
        super().__init__(
            ChromiumDesktopSourceDefinition(
                source_id="minimax-agent",
                display_name="MiniMax Agent",
                provider="minimax",
                env_name=TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV,
                app_names=("MiniMax Agent",),
                response_url_keywords=(
                    "agent.minimax.io/v1/api/",
                    "agent.minimax.io/api/",
                    "agent.minimax.io/api/v1/",
                ),
                usage_url_keywords=(
                    "agent.minimax.io/v1/api/chat/",
                    "agent.minimax.io/v1/api/assistant/",
                    "agent.minimax.io/v1/api/text/",
                    "agent.minimax.io/api/chat/",
                    "agent.minimax.io/api/v1/chat/",
                    "agent.minimax.io/api/v1/assistant/",
                    "agent.minimax.io/api/v1/text/",
                ),
            ),
            root=root or resolve_path_override(TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV, default_minimax_agent_root()),
        )
        self.parser_version = "minimax-agent-v2"
