from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from hashlib import md5
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_KIMI_CLI_ROOT_ENV,
    default_kimi_share_root,
    resolve_path_override,
)
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.time_window import within_window


def _normalize_kimi_token_usage(payload: dict[str, object]) -> dict[str, int]:
    input_other = int(payload.get("input_other", 0) or 0)
    input_cache_read = int(payload.get("input_cache_read", 0) or 0)
    input_cache_creation = int(payload.get("input_cache_creation", 0) or 0)
    output_tokens = int(payload.get("output", 0) or 0)
    input_tokens = input_other + input_cache_read + input_cache_creation
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": input_cache_read,
        "output_tokens": output_tokens,
        "reasoning_tokens": 0,
        "total_tokens": input_tokens + output_tokens,
    }


def _iter_kimi_events(message_type: str, payload: object) -> Iterator[tuple[str, dict[str, object]]]:
    if not isinstance(payload, dict):
        return
    if message_type == "SubagentEvent":
        inner = payload.get("event")
        if isinstance(inner, dict):
            inner_type = inner.get("type")
            inner_payload = inner.get("payload")
            if isinstance(inner_type, str):
                yield from _iter_kimi_events(inner_type, inner_payload)
        return
    yield message_type, payload


class KimiCliAdapter(BaseAdapter):
    source_id = "kimi-cli"
    display_name = "Kimi CLI"
    provider = "moonshotai"
    accuracy_level = "exact"
    parser_version = "kimi-cli-v1"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or resolve_path_override(
            TOKEN_USAGE_KIMI_CLI_ROOT_ENV,
            default_kimi_share_root(),
        )
        self.sessions_root = self.root / "sessions"
        self.metadata_file = self.root / "kimi.json"
        self._inventory: dict[str, object] | None = None

    def _wire_files(self) -> list[Path]:
        if not self.sessions_root.exists():
            return []
        return sorted(path for path in self.sessions_root.glob("*/*/wire.jsonl") if path.is_file())

    def _load_project_map(self) -> dict[str, str]:
        if not self.metadata_file.exists():
            return {}
        try:
            payload = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        result: dict[str, str] = {}
        work_dirs = payload.get("work_dirs")
        if not isinstance(work_dirs, list):
            return result

        for item in work_dirs:
            if not isinstance(item, dict):
                continue
            path_value = item.get("path")
            if not isinstance(path_value, str) or not path_value:
                continue
            kaos = str(item.get("kaos") or "local")
            digest = md5(path_value.encode("utf-8")).hexdigest()
            dirname = digest if kaos == "local" else f"{kaos}_{digest}"
            result[dirname] = path_value
        return result

    def _build_inventory(self) -> dict[str, object]:
        if self._inventory is not None:
            return self._inventory

        wire_files = self._wire_files()
        files_with_usage: list[Path] = []
        parse_issues: list[str] = []

        for path in wire_files:
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

                        if not isinstance(payload, dict) or payload.get("type") == "metadata":
                            continue

                        message = payload.get("message")
                        if not isinstance(message, dict):
                            continue

                        message_type = message.get("type")
                        message_payload = message.get("payload")
                        if not isinstance(message_type, str):
                            continue

                        found_usage = False
                        for event_type, event_payload in _iter_kimi_events(message_type, message_payload):
                            if event_type != "StatusUpdate":
                                continue
                            token_usage = event_payload.get("token_usage")
                            if isinstance(token_usage, dict):
                                files_with_usage.append(path)
                                found_usage = True
                                break
                        if found_usage:
                            break
            except OSError as exc:
                parse_issues.append(f"failed reading {path}: {exc}")

        self._inventory = {
            "wire_files": wire_files,
            "files_with_usage": sorted({path for path in files_with_usage}),
            "project_map": self._load_project_map(),
            "parse_issues": parse_issues,
        }
        return self._inventory

    def detect(self) -> SourceDetection:
        inventory = self._build_inventory()
        wire_files = list(inventory["wire_files"])
        files_with_usage = list(inventory["files_with_usage"])
        details: list[str] = []

        if files_with_usage:
            details.append("official wire.jsonl records expose StatusUpdate.token_usage events")
            details.append("session roots follow ~/.kimi/sessions/<workdir-hash>/<session-id>/wire.jsonl")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="Kimi CLI wire.jsonl files expose exact StatusUpdate token_usage events",
                candidate_paths=[str(files_with_usage[0]), str(self.root)],
                details=details,
            )

        if wire_files:
            details.append(f"detected {len(wire_files)} Kimi CLI wire.jsonl file(s)")
            details.append("none of the wire records exposed StatusUpdate.token_usage yet")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Kimi CLI wire files were found, but no exact token_usage records were present; "
                    f"override with {TOKEN_USAGE_KIMI_CLI_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(wire_files[0]), str(self.root)],
                details=details,
            )

        if self.root.exists():
            details.append("Kimi share root exists, but no sessions/*/*/wire.jsonl files were found")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "Kimi CLI share root exists, but no wire.jsonl sessions were found yet; "
                    f"override with {TOKEN_USAGE_KIMI_CLI_ROOT_ENV} if needed"
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
                "Kimi CLI share root not found; "
                f"check {TOKEN_USAGE_KIMI_CLI_ROOT_ENV} or upstream KIMI_SHARE_DIR"
            ),
            candidate_paths=[str(self.root)],
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        inventory = self._build_inventory()
        wire_files = list(inventory["wire_files"])
        if not wire_files:
            return SourceCollectResult(
                detection=detection,
                scanned_files=0,
                skipped_reasons=[detection.summary],
            )

        project_map = dict(inventory["project_map"])
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else datetime.now().astimezone().tzinfo
        )
        events: list[UsageEvent] = []
        verification_issues = list(inventory["parse_issues"])
        seen: set[tuple[str, str, int, int]] = set()

        for path in wire_files:
            workdir_hash = path.parent.parent.name
            project_path = project_map.get(workdir_hash)
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

                        if not isinstance(payload, dict) or payload.get("type") == "metadata":
                            continue

                        message = payload.get("message")
                        if not isinstance(message, dict):
                            continue
                        message_type = message.get("type")
                        message_payload = message.get("payload")
                        if not isinstance(message_type, str):
                            continue

                        try:
                            timestamp = datetime.fromtimestamp(float(payload.get("timestamp", 0)), tz=fallback_tz)
                        except (TypeError, ValueError, OSError) as exc:
                            verification_issues.append(f"invalid timestamp in {path}:{line_number}: {exc}")
                            continue

                        if not within_window(window, timestamp):
                            continue

                        for event_type, event_payload in _iter_kimi_events(message_type, message_payload):
                            if event_type != "StatusUpdate":
                                continue
                            token_usage = event_payload.get("token_usage")
                            if not isinstance(token_usage, dict):
                                continue

                            usage_values = _normalize_kimi_token_usage(token_usage)
                            if usage_values["total_tokens"] <= 0:
                                continue

                            session_id = path.parent.name
                            message_id = str(event_payload.get("message_id") or "")
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
                                    model=None,
                                    input_tokens=usage_values["input_tokens"],
                                    cached_input_tokens=usage_values["cached_input_tokens"],
                                    output_tokens=usage_values["output_tokens"],
                                    reasoning_tokens=usage_values["reasoning_tokens"],
                                    total_tokens=usage_values["total_tokens"],
                                    accuracy_level=self.accuracy_level,
                                    raw_event_kind="kimi_cli:status_update",
                                    source_path=str(path),
                                )
                            )
            except OSError as exc:
                verification_issues.append(f"failed reading {path}: {exc}")

        if not events and not verification_issues:
            verification_issues.append("no Kimi CLI token_usage events landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(wire_files),
            verification_issues=verification_issues,
            skipped_reasons=([detection.summary] if not events else []),
        )
