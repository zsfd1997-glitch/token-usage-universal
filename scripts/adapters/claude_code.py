from __future__ import annotations

import json
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
    default_claude_local_agent_root,
    resolve_path_override,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.time_window import parse_timestamp, within_window

_CLAUDE_TIMESTAMP_KEYS = ("executor_end", "grader_end")
_CLAUDE_LAYOUT_MARKER_NAMES = (".claude.json", "cowork_settings.json", "manifest.json")


class ClaudeCodeAdapter(BaseAdapter):
    source_id = "claude-code"
    display_name = "Claude Code"
    provider = "anthropic"
    accuracy_level = "exact"

    def __init__(
        self,
        *,
        transcript_root: Path | None = None,
        local_agent_root: Path | None = None,
    ) -> None:
        self.transcript_root = transcript_root or resolve_path_override(
            TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
            Path.home() / ".claude" / "transcripts",
        )
        self.local_agent_root = local_agent_root or resolve_path_override(
            TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
            default_claude_local_agent_root(),
        )
        self._local_agent_inventory: dict[str, object] | None = None

    def _transcript_files(self) -> list[Path]:
        if not self.transcript_root.exists():
            return []
        return sorted(self.transcript_root.glob("*.jsonl"))

    def _local_agent_json_files(self) -> list[Path]:
        if not self.local_agent_root.exists():
            return []
        matches: list[Path] = []
        for pattern in ("*.json", ".*.json"):
            matches.extend(path for path in self.local_agent_root.rglob(pattern) if path.is_file())
        return sorted({path for path in matches})

    def _build_local_agent_inventory(self) -> dict[str, object]:
        if self._local_agent_inventory is not None:
            return self._local_agent_inventory

        json_files = self._local_agent_json_files()
        exact_files: list[Path] = []
        candidate_files: list[Path] = []
        marker_files: list[Path] = []
        parse_issues: list[str] = []

        for path in json_files:
            if path.name in _CLAUDE_LAYOUT_MARKER_NAMES and len(marker_files) < 5:
                marker_files.append(path)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                parse_issues.append(f"failed parsing {path}: {exc}")
                continue

            if not isinstance(payload, dict):
                continue

            total_tokens = payload.get("total_tokens")
            has_timestamp = any(payload.get(key) not in (None, "") for key in _CLAUDE_TIMESTAMP_KEYS)
            if "timing" in path.name.lower() or total_tokens not in (None, "") or has_timestamp:
                candidate_files.append(path)
            if total_tokens not in (None, "") and has_timestamp:
                exact_files.append(path)

        self._local_agent_inventory = {
            "json_files": json_files,
            "candidate_files": candidate_files,
            "exact_files": exact_files,
            "marker_files": marker_files,
            "parse_issues": parse_issues,
        }
        return self._local_agent_inventory

    def detect(self) -> SourceDetection:
        transcripts = self._transcript_files()
        inventory = self._build_local_agent_inventory()
        exact_files = list(inventory["exact_files"])
        marker_files = list(inventory["marker_files"])
        json_files = list(inventory["json_files"])
        candidate_paths = [str(path) for path in exact_files[:2] + transcripts[:1]]
        details: list[str] = []

        if exact_files:
            details.append("supports old timing.json and any Claude JSON that exposes total_tokens + executor_end/grader_end")
            details.append("Claude exact JSON does not expose input/output/cache breakdown fields")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="captured Claude exact JSON files found for exact total-token collection",
                candidate_paths=candidate_paths,
                details=details,
            )

        if json_files:
            marker_names = ", ".join(sorted({path.name for path in marker_files})) or "session/config JSONs"
            details.append(f"detected local-agent JSON layout markers: {marker_names}")
            details.append("none of the JSON files under local-agent-mode-sessions expose both total_tokens and executor_end/grader_end")
            if transcripts:
                details.append("transcripts are text-only and cannot recover exact totals")
            details.append("local transcripts are text-only and do not contain exact token usage fields")
            details.append("Claude exact totals are only recoverable when local-agent-mode-sessions persisted a token-bearing exact JSON")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Claude local-agent layout detected, but no token-bearing exact JSON was found; "
                    f"override with {TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(self.local_agent_root), *[str(path) for path in marker_files[:2]], *candidate_paths][:5],
                details=details,
            )

        if transcripts:
            details.append("local transcripts are text-only and do not contain exact token usage fields")
            details.append("Claude exact totals need a token-bearing local-agent JSON (old builds commonly used timing.json)")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "transcripts detected, but no Claude exact JSON was found for total-token collection; "
                    f"override with {TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(path) for path in transcripts[:1]] + [str(self.transcript_root), str(self.local_agent_root)],
                details=details,
            )

        if self.local_agent_root.exists():
            details.append("local-agent-mode-sessions directory exists, but no JSON files with total_tokens + executor_end/grader_end were found")
            details.append("older Claude builds commonly persisted timing.json; newer layouts may only keep session/config artifacts")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="Claude local session directory exists, but no exact JSON records were found yet",
                candidate_paths=[str(self.local_agent_root)],
                details=details,
            )

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=False,
            summary=(
                "Claude local traces not found; "
                f"check {TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV} / {TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV}"
            ),
            candidate_paths=[str(self.transcript_root), str(self.local_agent_root)],
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        inventory = self._build_local_agent_inventory()
        json_files = list(inventory["json_files"])
        candidate_files = list(inventory["candidate_files"])
        if not candidate_files:
            return SourceCollectResult(
                detection=detection,
                scanned_files=len(json_files),
                verification_issues=(
                    ["inspected local-agent JSON files, but none exposed total_tokens + executor_end/grader_end"]
                    if json_files
                    else []
                ),
                skipped_reasons=[detection.summary],
            )

        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in candidate_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                verification_issues.append(f"failed parsing {path}: {exc}")
                continue

            total_tokens = payload.get("total_tokens")
            timestamp_value = payload.get("executor_end") or payload.get("grader_end")
            if total_tokens in (None, "") or timestamp_value in (None, ""):
                verification_issues.append(f"missing total_tokens or executor_end/grader_end in {path}")
                continue

            try:
                timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                total_value = int(total_tokens)
            except (TypeError, ValueError) as exc:
                verification_issues.append(f"invalid timing payload in {path}: {exc}")
                continue

            if not within_window(window, timestamp):
                continue

            events.append(
                UsageEvent(
                    source=self.source_id,
                    provider=self.provider,
                    timestamp=timestamp,
                    session_id=path.parent.name,
                    project_path=None,
                    model=None,
                    input_tokens=None,
                    cached_input_tokens=None,
                    output_tokens=None,
                    reasoning_tokens=None,
                    total_tokens=total_value,
                    accuracy_level=self.accuracy_level,
                    raw_event_kind=f"{path.name}:session_total",
                    source_path=str(path),
                )
            )

        if events:
            verification_issues.append(
                "Claude exact JSON only provides total_tokens; input/output/cache breakdown is unavailable"
            )
        elif not verification_issues:
            verification_issues.append("no Claude exact JSON sessions landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(candidate_files),
            verification_issues=verification_issues[:10],
        )
