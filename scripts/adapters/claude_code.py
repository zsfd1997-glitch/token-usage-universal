from __future__ import annotations

import json
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV,
    TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT_ENV,
    resolve_path_override,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.time_window import parse_timestamp, within_window


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
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "local-agent-mode-sessions",
        )

    def _transcript_files(self) -> list[Path]:
        if not self.transcript_root.exists():
            return []
        return sorted(self.transcript_root.glob("*.jsonl"))

    def _timing_files(self) -> list[Path]:
        if not self.local_agent_root.exists():
            return []
        return sorted(self.local_agent_root.rglob("timing.json"))

    def detect(self) -> SourceDetection:
        transcripts = self._transcript_files()
        timing_files = self._timing_files()
        candidate_paths = [str(path) for path in timing_files[:2] + transcripts[:1]]
        details: list[str] = []

        if timing_files:
            details.append("timing.json exposes total_tokens and executor_end for finished local runs")
            details.append("Claude timing.json does not expose input/output/cache breakdown fields")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="captured timing.json files found for exact total-token collection",
                candidate_paths=candidate_paths,
                details=details,
            )

        if transcripts:
            details.append("local transcripts are text-only and do not contain exact token usage fields")
            details.append("Claude exact totals are only recoverable when task notifications were persisted into timing.json")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "transcripts detected, but no timing.json captured for exact totals; "
                    f"override with {TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT_ENV} if needed"
                ),
                candidate_paths=candidate_paths or [str(self.transcript_root)],
                details=details,
            )

        if self.local_agent_root.exists():
            details.append("local-agent-mode-sessions directory exists, but no timing.json files were found")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="Claude local session artifacts found, but no exact timing.json records yet",
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
        timing_files = self._timing_files()
        if not timing_files:
            return SourceCollectResult(
                detection=detection,
                scanned_files=0,
                skipped_reasons=[detection.summary],
            )

        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in timing_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                verification_issues.append(f"failed parsing {path}: {exc}")
                continue

            total_tokens = payload.get("total_tokens")
            timestamp_value = payload.get("executor_end") or payload.get("grader_end")
            if total_tokens in (None, "") or timestamp_value in (None, ""):
                verification_issues.append(f"missing total_tokens or executor_end in {path}")
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
                    raw_event_kind="timing.json:session_total",
                    source_path=str(path),
                )
            )

        if events:
            verification_issues.append(
                "Claude timing.json only provides total_tokens; input/output/cache breakdown is unavailable"
            )
        elif not verification_issues:
            verification_issues.append("no Claude timing.json sessions landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(timing_files),
            verification_issues=verification_issues[:10],
        )
