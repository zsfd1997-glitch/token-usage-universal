from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_QWEN_CODE_ROOT_ENV,
    default_qwen_runtime_root,
    resolve_path_override,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.pricing import PricingDatabase
from core.time_window import parse_timestamp, within_window


def _normalize_usage_metadata(payload: dict[str, object]) -> dict[str, int]:
    input_tokens = int(payload.get("promptTokenCount", 0) or 0)
    cached_input_tokens = int(payload.get("cachedContentTokenCount", 0) or 0)
    output_tokens = int(payload.get("candidatesTokenCount", 0) or 0)
    reasoning_tokens = int(payload.get("thoughtsTokenCount", 0) or 0)
    total_tokens = int(payload.get("totalTokenCount", 0) or 0)
    if not total_tokens:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


class QwenCodeCliAdapter(BaseAdapter):
    source_id = "qwen-code-cli"
    display_name = "Qwen Code CLI"
    provider = "qwen"
    accuracy_level = "exact"
    parser_version = "qwen-code-cli-v1"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or resolve_path_override(
            TOKEN_USAGE_QWEN_CODE_ROOT_ENV,
            default_qwen_runtime_root(),
        )
        self._inventory: dict[str, object] | None = None

    def _chat_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        matches: list[Path] = []
        for pattern in ("projects/*/chats/*.jsonl", "tmp/*/chats/*.jsonl"):
            matches.extend(path for path in self.root.glob(pattern) if path.is_file())
        return sorted({path for path in matches})

    def _build_inventory(self) -> dict[str, object]:
        if self._inventory is not None:
            return self._inventory

        chat_files = self._chat_files()
        files_with_usage: list[Path] = []
        parse_issues: list[str] = []

        for path in chat_files:
            try:
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            payload = json.loads(stripped)
                        except json.JSONDecodeError as exc:
                            parse_issues.append(f"failed parsing {path}: {exc}")
                            break
                        if not isinstance(payload, dict):
                            continue
                        usage_metadata = payload.get("usageMetadata")
                        if payload.get("type") == "assistant" and isinstance(usage_metadata, dict):
                            files_with_usage.append(path)
                            break
            except OSError as exc:
                parse_issues.append(f"failed reading {path}: {exc}")

        self._inventory = {
            "chat_files": chat_files,
            "files_with_usage": sorted({path for path in files_with_usage}),
            "parse_issues": parse_issues,
        }
        return self._inventory

    def detect(self) -> SourceDetection:
        inventory = self._build_inventory()
        chat_files = list(inventory["chat_files"])
        files_with_usage = list(inventory["files_with_usage"])
        details: list[str] = []

        if files_with_usage:
            details.append("project-scoped JSONL session files expose assistant usageMetadata records")
            details.append("supports both current ~/.qwen/projects/*/chats and legacy ~/.qwen/tmp/*/chats layouts")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="Qwen Code CLI session JSONL files expose exact usageMetadata records",
                candidate_paths=[str(files_with_usage[0]), str(self.root)],
                details=details,
            )

        if chat_files:
            details.append(f"detected {len(chat_files)} Qwen session JSONL file(s)")
            details.append("none of the assistant records exposed usageMetadata yet")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Qwen Code CLI session files were found, but no exact usageMetadata records were present; "
                    f"override with {TOKEN_USAGE_QWEN_CODE_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(chat_files[0]), str(self.root)],
                details=details,
            )

        if self.root.exists():
            details.append("Qwen runtime root exists, but no session JSONL files were found under projects/*/chats or tmp/*/chats")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Qwen Code runtime root exists, but no session JSONL files were found yet; "
                    f"override with {TOKEN_USAGE_QWEN_CODE_ROOT_ENV} if needed"
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
            summary=(
                "Qwen Code CLI runtime root not found; "
                f"check {TOKEN_USAGE_QWEN_CODE_ROOT_ENV} or upstream QWEN_RUNTIME_DIR"
            ),
            candidate_paths=[str(self.root)],
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        inventory = self._build_inventory()
        chat_files = list(inventory["chat_files"])
        if not chat_files:
            return SourceCollectResult(
                detection=detection,
                scanned_files=0,
                skipped_reasons=[detection.summary],
            )

        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else datetime.now().astimezone().tzinfo
        )
        events: list[UsageEvent] = []
        verification_issues = list(inventory["parse_issues"])
        seen: set[tuple[str, str, str, int, int]] = set()
        used_file_timestamp = False

        for path in chat_files:
            try:
                with path.open(encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            payload = json.loads(stripped)
                        except json.JSONDecodeError as exc:
                            verification_issues.append(f"failed parsing {path}:{line_number}: {exc}")
                            break

                        if not isinstance(payload, dict) or payload.get("type") != "assistant":
                            continue

                        usage_metadata = payload.get("usageMetadata")
                        if not isinstance(usage_metadata, dict):
                            continue

                        usage_values = _normalize_usage_metadata(usage_metadata)
                        if usage_values["total_tokens"] <= 0:
                            continue

                        timestamp_value = payload.get("timestamp")
                        if timestamp_value not in (None, ""):
                            try:
                                timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                            except (TypeError, ValueError) as exc:
                                verification_issues.append(f"invalid timestamp in {path}:{line_number}: {exc}")
                                continue
                        else:
                            timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=fallback_tz)
                            used_file_timestamp = True

                        if not within_window(window, timestamp):
                            continue

                        raw_model = payload.get("model")
                        canonical_model = pricing.canonical_model(raw_model, self.provider) if raw_model else None
                        normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
                        model_resolution = "unknown"
                        if canonical_model:
                            model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

                        session_id = str(payload.get("sessionId") or path.stem)
                        dedupe_key = (
                            session_id,
                            canonical_model or str(raw_model or ""),
                            str(path),
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
                                project_path=str(payload.get("cwd")) if payload.get("cwd") not in (None, "") else None,
                                model=canonical_model or (str(raw_model) if raw_model not in (None, "") else None),
                                input_tokens=usage_values["input_tokens"],
                                cached_input_tokens=usage_values["cached_input_tokens"],
                                output_tokens=usage_values["output_tokens"],
                                reasoning_tokens=usage_values["reasoning_tokens"],
                                total_tokens=usage_values["total_tokens"],
                                accuracy_level=self.accuracy_level,
                                raw_event_kind="qwen_code_cli:usage_metadata",
                                source_path=str(path),
                                raw_model=str(raw_model) if raw_model not in (None, "") else None,
                                model_resolution=model_resolution,
                                model_source="qwen_chat_record" if raw_model not in (None, "") else None,
                            )
                        )
            except OSError as exc:
                verification_issues.append(f"failed reading {path}: {exc}")

        if used_file_timestamp:
            verification_issues.append("some Qwen session records lacked timestamps, so file modification time was used as a fallback")
        if not events and not verification_issues:
            verification_issues.append("no Qwen Code CLI usage events landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(chat_files),
            verification_issues=verification_issues,
            skipped_reasons=([detection.summary] if not events else []),
        )
