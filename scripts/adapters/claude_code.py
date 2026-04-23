from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
    default_claude_local_agent_root,
    resolve_path_override,
    safe_home_path,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.robust_read import read_json_robust, read_text_robust
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
            safe_home_path() / ".claude" / "transcripts",
        )
        self.project_root = self.transcript_root.parent / "projects"
        self.local_agent_root = local_agent_root or resolve_path_override(
            TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
            default_claude_local_agent_root(),
        )
        self._local_agent_inventory: dict[str, object] | None = None

    def _transcript_files(self) -> list[Path]:
        if not self.transcript_root.exists():
            return []
        return sorted(self.transcript_root.glob("*.jsonl"))

    def _project_session_files(self) -> list[Path]:
        if not self.project_root.exists():
            return []
        return sorted(path for path in self.project_root.rglob("*.jsonl") if path.is_file())

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
            payload, _enc = read_json_robust(path)
            if payload is None:
                parse_issues.append(f"failed parsing {path}")
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

    def _collect_project_usage_events(self, window=None) -> tuple[list[UsageEvent], list[str], list[Path]]:
        project_files = self._project_session_files()
        if not project_files:
            return [], [], []

        events: list[UsageEvent] = []
        issues: list[str] = []
        fallback_tz = (
            window.start.tzinfo
            if window and window.start
            else datetime.now().astimezone().tzinfo
        )

        for path in project_files:
            text, _enc = read_text_robust(path)
            if text is None:
                issues.append(f"failed reading {path}")
                continue
            lines = text.splitlines()

            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    issues.append(f"failed parsing {path}:{line_number}: {exc}")
                    continue

                if not isinstance(payload, dict) or payload.get("type") != "assistant":
                    continue

                message = payload.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue

                input_tokens = int(usage.get("input_tokens") or 0)
                cache_creation_tokens = int(usage.get("cache_creation_input_tokens") or 0)
                cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or 0)
                total_tokens = input_tokens + cache_creation_tokens + cache_read_tokens + output_tokens
                if total_tokens <= 0:
                    continue

                timestamp_value = payload.get("timestamp")
                if timestamp_value in (None, ""):
                    issues.append(f"missing timestamp in {path}:{line_number}")
                    continue

                try:
                    timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                except (TypeError, ValueError) as exc:
                    issues.append(f"invalid timestamp in {path}:{line_number}: {exc}")
                    continue

                if window and not within_window(window, timestamp):
                    continue

                model = message.get("model")
                session_id = str(payload.get("sessionId") or path.stem)
                project_path = payload.get("cwd")
                events.append(
                    UsageEvent(
                        source=self.source_id,
                        provider=self.provider,
                        timestamp=timestamp,
                        session_id=session_id,
                        project_path=str(project_path) if project_path else None,
                        model=str(model) if model else None,
                        input_tokens=input_tokens + cache_creation_tokens,
                        cached_input_tokens=cache_read_tokens,
                        output_tokens=output_tokens,
                        reasoning_tokens=None,
                        total_tokens=total_tokens,
                        accuracy_level=self.accuracy_level,
                        raw_event_kind=f"{path.name}:assistant_usage",
                        source_path=str(path),
                        raw_model=str(model) if model else None,
                        model_resolution="exact" if model else "unknown",
                        model_source="message.model" if model else None,
                    )
                )

        return events, issues, project_files

    def detect(self) -> SourceDetection:
        transcripts = self._transcript_files()
        project_events, project_issues, project_files = self._collect_project_usage_events()
        inventory = self._build_local_agent_inventory()
        exact_files = list(inventory["exact_files"])
        marker_files = list(inventory["marker_files"])
        json_files = list(inventory["json_files"])
        candidate_paths = [str(path) for path in exact_files[:2] + project_files[:2] + transcripts[:1]]
        details: list[str] = []

        if project_events:
            details.append(f"detected {len(project_files)} Claude project JSONL file(s)")
            details.append("project assistant messages expose exact usage and model fields")
            details.extend(project_issues[:3])
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="Claude project JSONL files found with exact usage payloads",
                candidate_paths=candidate_paths[:5],
                details=details,
            )

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
                candidate_paths=candidate_paths[:5],
                details=details,
            )

        if json_files:
            marker_names = ", ".join(sorted({path.name for path in marker_files})) or "session/config JSONs"
            details.append(f"detected local-agent JSON layout markers: {marker_names}")
            details.append("none of the JSON files under local-agent-mode-sessions expose both total_tokens and executor_end/grader_end")
            if project_files:
                details.append("project JSONL files were found, but none exposed positive exact usage payloads")
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

        if project_files or transcripts:
            if project_files:
                details.append("project JSONL files were found, but none exposed positive exact usage payloads")
            if transcripts:
                details.append("local transcripts are text-only and do not contain exact token usage fields")
            details.append("Claude exact totals need a token-bearing project JSONL usage payload or local-agent exact JSON")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Claude traces detected, but no exact Claude usage payload was found for total-token collection; "
                    f"override with {TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV} if needed"
                ),
                candidate_paths=candidate_paths[:5] + [str(self.transcript_root), str(self.local_agent_root)],
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
            candidate_paths=[str(self.transcript_root), str(self.project_root), str(self.local_agent_root)],
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        project_events, project_issues, project_files = self._collect_project_usage_events(window)
        inventory = self._build_local_agent_inventory()
        json_files = list(inventory["json_files"])
        candidate_files = list(inventory["candidate_files"])
        if not candidate_files and not project_events:
            verification_issues = []
            if json_files:
                verification_issues.append("inspected local-agent JSON files, but none exposed total_tokens + executor_end/grader_end")
            verification_issues.extend(project_issues)
            return SourceCollectResult(
                detection=detection,
                scanned_files=len(json_files) + len(project_files),
                verification_issues=verification_issues[:10],
                skipped_reasons=[detection.summary],
            )

        events: list[UsageEvent] = list(project_events)
        verification_issues: list[str] = list(project_issues)
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else datetime.now().astimezone().tzinfo
        )

        for path in candidate_files:
            payload, _enc = read_json_robust(path)
            if payload is None:
                verification_issues.append(f"failed parsing {path}")
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

        if any(event.raw_event_kind.endswith(":session_total") for event in events):
            verification_issues.append(
                "Claude exact JSON only provides total_tokens; input/output/cache breakdown is unavailable"
            )
        elif not events and not verification_issues:
            verification_issues.append("no Claude exact usage events landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=sorted(events, key=lambda event: event.timestamp),
            scanned_files=len(candidate_files) + len(project_files),
            verification_issues=verification_issues[:10],
        )
