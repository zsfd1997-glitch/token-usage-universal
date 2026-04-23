from __future__ import annotations

import re
from pathlib import Path

from adapters.chromium_desktop import ChromiumDesktopAdapter, ChromiumDesktopSourceDefinition
from core.config import TOKEN_USAGE_CLAUDE_DESKTOP_ROOT_ENV
from core.models import SourceDetection


_CLAUDE_MODEL_TRACE_RE = re.compile(
    rb"(claude-(?:sonnet|haiku|opus)[a-z0-9._-]*|(?:sonnet|haiku|opus)-[a-z0-9._-]+)",
    re.IGNORECASE,
)


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

    def _raw_model_traces(self) -> list[str]:
        roots = self._existing_roots()
        if not roots:
            return []

        traces: list[str] = []
        seen: set[str] = set()
        raw_files: list[Path] = []
        for root in roots:
            raw_files.extend(self._indexeddb_files(root))
            raw_files.extend(self._local_storage_files(root))
            session_storage = root / "Session Storage"
            if session_storage.exists():
                raw_files.extend(path for path in session_storage.iterdir() if path.is_file())

        for path in raw_files[:40]:
            try:
                payload = path.read_bytes()
            except OSError:
                continue
            for match in _CLAUDE_MODEL_TRACE_RE.findall(payload):
                model = match.decode("utf-8", errors="ignore").lower().strip(" \"'.,:;[](){}")
                if not model:
                    continue
                if not model.startswith("claude-") and "-" in model:
                    model = f"claude-{model}"
                if model in seen:
                    continue
                seen.add(model)
                traces.append(model)
                if len(traces) >= 5:
                    return traces
        return traces

    def detect(self) -> SourceDetection:
        detection = super().detect()
        if detection.available:
            return detection

        model_traces = self._raw_model_traces()
        if not model_traces:
            return detection

        details = ["detected model traces in desktop stores: " + ", ".join(model_traces)]
        details.extend(detection.details)
        return SourceDetection(
            source_id=detection.source_id,
            display_name=detection.display_name,
            provider=detection.provider,
            accuracy_level=detection.accuracy_level,
            supported=detection.supported,
            available=detection.available,
            summary=detection.summary,
            candidate_paths=detection.candidate_paths,
            details=details,
        )
