from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_GEMINI_CLI_ROOT_ENV,
    default_gemini_cli_root,
    resolve_path_override,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.pricing import PricingDatabase
from core.robust_read import read_json_robust, read_text_robust
from core.time_window import parse_timestamp, within_window


def _normalize_gemini_message_tokens(payload: dict[str, object]) -> dict[str, int]:
    prompt_tokens = int(payload.get("input", 0) or 0)
    tool_tokens = int(payload.get("tool", 0) or 0)
    cached_tokens = int(payload.get("cached", 0) or 0)
    output_tokens = int(payload.get("output", 0) or 0)
    reasoning_tokens = int(payload.get("thoughts", 0) or 0)
    total_tokens = int(payload.get("total", 0) or 0)
    input_tokens = prompt_tokens + tool_tokens
    if not total_tokens:
        total_tokens = input_tokens + output_tokens + reasoning_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


class GeminiCliAdapter(BaseAdapter):
    source_id = "gemini-cli"
    display_name = "Gemini CLI"
    provider = "google"
    accuracy_level = "exact"
    parser_version = "gemini-cli-v1"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or resolve_path_override(
            TOKEN_USAGE_GEMINI_CLI_ROOT_ENV,
            default_gemini_cli_root(),
        )
        self.tmp_root = self.root / "tmp"
        self._inventory: dict[str, object] | None = None

    def _session_files(self) -> list[Path]:
        if not self.tmp_root.exists():
            return []
        return sorted(path for path in self.tmp_root.glob("*/chats/session-*.json") if path.is_file())

    def _load_project_root_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if not self.tmp_root.exists():
            return result
        for marker in self.tmp_root.glob("*/.project_root"):
            if not marker.is_file():
                continue
            text, _enc = read_text_robust(marker)
            if text is None:
                continue
            project_root = text.strip()
            if project_root:
                result[marker.parent.name] = project_root
        return result

    def _build_inventory(self) -> dict[str, object]:
        if self._inventory is not None:
            return self._inventory

        session_files = self._session_files()
        files_with_usage: list[Path] = []
        parse_issues: list[str] = []

        for path in session_files:
            payload, _enc = read_json_robust(path)
            if payload is None:
                parse_issues.append(f"failed parsing {path}")
                continue

            if not isinstance(payload, dict):
                continue

            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue

            for message in messages:
                if not isinstance(message, dict) or message.get("type") != "gemini":
                    continue
                tokens = message.get("tokens")
                if not isinstance(tokens, dict):
                    continue
                if _normalize_gemini_message_tokens(tokens)["total_tokens"] > 0:
                    files_with_usage.append(path)
                    break

        self._inventory = {
            "session_files": session_files,
            "files_with_usage": sorted({path for path in files_with_usage}),
            "project_roots": self._load_project_root_map(),
            "parse_issues": parse_issues,
        }
        return self._inventory

    def detect(self) -> SourceDetection:
        inventory = self._build_inventory()
        session_files = list(inventory["session_files"])
        files_with_usage = list(inventory["files_with_usage"])
        details: list[str] = []

        if files_with_usage:
            details.append("official Gemini session JSON files expose per-message tokens on assistant responses")
            details.append("session roots follow ~/.gemini/tmp/<project-id>/chats/session-*.json")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="Gemini CLI session JSON files expose exact per-message token records",
                candidate_paths=[str(files_with_usage[0]), str(self.root)],
                details=details,
            )

        if session_files:
            details.append(f"detected {len(session_files)} Gemini session file(s)")
            details.append("none of the recorded Gemini assistant messages exposed non-zero tokens yet")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Gemini CLI session files were found, but no exact token-bearing assistant messages were present; "
                    f"override with {TOKEN_USAGE_GEMINI_CLI_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(session_files[0]), str(self.root)],
                details=details,
            )

        if self.root.exists():
            details.append("Gemini CLI runtime root exists, but no tmp/*/chats/session-*.json files were found")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Gemini CLI runtime root exists, but no session JSON files were found yet; "
                    f"override with {TOKEN_USAGE_GEMINI_CLI_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(self.root)],
                details=details,
            )

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=False,
            summary=f"Gemini CLI runtime root not found; check {TOKEN_USAGE_GEMINI_CLI_ROOT_ENV}",
            candidate_paths=[str(self.root)],
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        inventory = self._build_inventory()
        session_files = list(inventory["session_files"])
        if not session_files:
            return SourceCollectResult(
                detection=detection,
                scanned_files=0,
                skipped_reasons=[detection.summary],
            )

        pricing = PricingDatabase()
        project_roots = dict(inventory["project_roots"])
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else datetime.now().astimezone().tzinfo
        )
        events: list[UsageEvent] = []
        verification_issues = list(inventory["parse_issues"])
        seen: set[tuple[str, str, int, int]] = set()
        used_file_timestamp = False

        for path in session_files:
            project_key = path.parent.parent.name
            project_path = project_roots.get(project_key)
            payload, _enc = read_json_robust(path)
            if payload is None:
                verification_issues.append(f"failed parsing {path}")
                continue

            if not isinstance(payload, dict):
                continue

            messages = payload.get("messages")
            if not isinstance(messages, list):
                continue

            session_id = str(payload.get("sessionId") or payload.get("session_id") or path.stem)

            for message_index, message in enumerate(messages, start=1):
                if not isinstance(message, dict) or message.get("type") != "gemini":
                    continue

                tokens = message.get("tokens")
                if not isinstance(tokens, dict):
                    continue

                usage_values = _normalize_gemini_message_tokens(tokens)
                if usage_values["total_tokens"] <= 0:
                    continue

                timestamp_value = message.get("timestamp") or payload.get("lastUpdated")
                if timestamp_value not in (None, ""):
                    try:
                        timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                    except (TypeError, ValueError) as exc:
                        verification_issues.append(f"invalid timestamp in {path} message {message_index}: {exc}")
                        continue
                else:
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=fallback_tz)
                    used_file_timestamp = True

                if not within_window(window, timestamp):
                    continue

                raw_model = message.get("model")
                canonical_model = pricing.canonical_model(raw_model, self.provider) if raw_model else None
                normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
                model_resolution = "unknown"
                if canonical_model:
                    model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

                message_id = str(message.get("id") or f"{session_id}:{message_index}")
                dedupe_key = (
                    session_id,
                    message_id,
                    usage_values["total_tokens"],
                    int(timestamp.timestamp()),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                events.append(
                    UsageEvent(
                        source=self.source_id,
                        provider=self.provider,
                        timestamp=timestamp,
                        session_id=session_id,
                        project_path=project_path,
                        model=canonical_model or (str(raw_model) if raw_model not in (None, "") else None),
                        input_tokens=usage_values["input_tokens"],
                        cached_input_tokens=usage_values["cached_input_tokens"],
                        output_tokens=usage_values["output_tokens"],
                        reasoning_tokens=usage_values["reasoning_tokens"],
                        total_tokens=usage_values["total_tokens"],
                        accuracy_level=self.accuracy_level,
                        raw_event_kind="gemini_cli:message_tokens",
                        source_path=str(path),
                        raw_model=str(raw_model) if raw_model not in (None, "") else None,
                        model_resolution=model_resolution,
                        model_source="gemini_chat_record" if raw_model not in (None, "") else None,
                    )
                )

        if used_file_timestamp:
            verification_issues.append(
                "some Gemini CLI messages lacked timestamps, so file modification time was used as a fallback"
            )
        if not events and not verification_issues:
            verification_issues.append("no Gemini CLI token-bearing messages landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(session_files),
            verification_issues=verification_issues,
            skipped_reasons=([detection.summary] if not events else []),
        )
