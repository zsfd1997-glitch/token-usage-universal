from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.time_window import parse_timestamp, within_window


_TIMESTAMP_KEYS = ("timestamp", "created_at", "time")
_SESSION_KEYS = ("session_id", "conversation_id", "request_id", "id")
_PROJECT_KEYS = ("project_path", "cwd", "project")
_PROVIDER_KEYS = ("provider", "model_provider", "vendor")
_MODEL_KEYS = ("model", "model_name")


def _flatten_candidates(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _find_first_value(node, keys: tuple[str, ...]):
    if isinstance(node, dict):
        for key in keys:
            if key in node and node[key] not in (None, ""):
                return node[key]
        for value in node.values():
            found = _find_first_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_first_value(value, keys)
            if found not in (None, ""):
                return found
    return None


def _find_usage_dict(node):
    if isinstance(node, dict):
        has_input = "input_tokens" in node or "prompt_tokens" in node
        has_output = "output_tokens" in node or "completion_tokens" in node
        has_total = "total_tokens" in node
        if has_total and (has_input or has_output):
            return node
        for value in node.values():
            found = _find_usage_dict(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_usage_dict(value)
            if found:
                return found
    return None


def _normalize_usage(payload: dict[str, object]) -> dict[str, int]:
    input_tokens = int(payload.get("input_tokens", payload.get("prompt_tokens", 0)) or 0)
    cached_input_tokens = int(payload.get("cached_input_tokens", 0) or 0)
    output_tokens = int(payload.get("output_tokens", payload.get("completion_tokens", 0)) or 0)
    reasoning_tokens = int(
        payload.get("reasoning_tokens", payload.get("reasoning_output_tokens", 0)) or 0
    )
    total_tokens = int(payload.get("total_tokens", input_tokens + output_tokens) or 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


class GenericOpenAICompatibleAdapter(BaseAdapter):
    source_id = "generic-openai-compatible"
    display_name = "Generic OpenAI Compatible"
    provider = "openai-compatible"
    accuracy_level = "exact"

    def __init__(self) -> None:
        self.glob_env = TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV

    def _resolve_paths(self) -> list[Path]:
        patterns = _flatten_candidates(os.environ.get(self.glob_env, ""))
        paths: list[Path] = []
        for pattern in patterns:
            matches = glob.glob(os.path.expanduser(pattern), recursive=True)
            paths.extend(Path(match) for match in matches)
        return sorted({path for path in paths if path.is_file()})

    def detect(self) -> SourceDetection:
        configured_paths = self._resolve_paths()
        if not configured_paths:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=f"set {self.glob_env} to enable explicit generic logs",
            )

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=True,
            summary="configured generic logs found",
            candidate_paths=[str(path) for path in configured_paths[:2]],
        )

    def _iter_records(self, path: Path):
        if path.suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    yield json.loads(raw_line)
            return

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            for item in payload:
                yield item
        else:
            yield payload

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(detection=detection, skipped_reasons=[detection.summary])

        paths = self._resolve_paths()
        events: list[UsageEvent] = []
        verification_issues: list[str] = []

        for path in paths:
            try:
                for record in self._iter_records(path):
                    usage = _find_usage_dict(record)
                    timestamp_value = _find_first_value(record, _TIMESTAMP_KEYS)
                    if not usage or not timestamp_value:
                        continue
                    usage_values = _normalize_usage(usage)
                    timestamp = parse_timestamp(
                        str(timestamp_value),
                        window.start.tzinfo if window.start else __import__("datetime").datetime.now().astimezone().tzinfo,
                    )
                    if not within_window(window, timestamp):
                        continue
                    events.append(
                        UsageEvent(
                            source=self.source_id,
                            provider=str(_find_first_value(record, _PROVIDER_KEYS) or self.provider),
                            timestamp=timestamp,
                            session_id=str(_find_first_value(record, _SESSION_KEYS) or path.stem),
                            project_path=_find_first_value(record, _PROJECT_KEYS),
                            model=_find_first_value(record, _MODEL_KEYS),
                            input_tokens=usage_values["input_tokens"],
                            cached_input_tokens=usage_values["cached_input_tokens"],
                            output_tokens=usage_values["output_tokens"],
                            reasoning_tokens=usage_values["reasoning_tokens"],
                            total_tokens=usage_values["total_tokens"],
                            accuracy_level=self.accuracy_level,
                            raw_event_kind="generic_usage:delta",
                            source_path=str(path),
                        )
                    )
            except (OSError, json.JSONDecodeError) as exc:
                verification_issues.append(f"failed parsing {path}: {exc}")

        if not events:
            verification_issues.append("no exact usage records found in configured generic logs")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(paths),
            verification_issues=verification_issues[:10],
        )
