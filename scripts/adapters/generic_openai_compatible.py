from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from adapters.base import BaseAdapter
from core.day_rollup import build_day_rollups, day_key, split_window_days
from core.config import (
    TOKEN_USAGE_DISCOVERY_ROOTS_ENV,
    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV,
    default_discovery_roots,
    expand_path_text,
)
from core.file_cache import FileEventCache
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.pricing import PricingDatabase
from core.time_window import parse_timestamp, within_window
from core.usage_records import (
    MODEL_KEYS,
    PROJECT_KEYS,
    PROVIDER_KEYS,
    SESSION_KEYS,
    TIMESTAMP_KEYS,
    find_first_value,
    find_usage_dict,
    normalize_usage,
)
_DISCOVERY_KEYWORDS = (
    "anthropic",
    "bigmodel",
    "dashscope",
    "glm",
    "helicone",
    "kimi",
    "langfuse",
    "litellm",
    "llm",
    "minimax",
    "moonshot",
    "openai",
    "opencode",
    "qwen",
    "zhipu",
)
_DISCOVERY_FILE_PATTERNS = (
    "*.jsonl",
    "*export*.json",
    "*export*.jsonl",
    "*history*.jsonl",
    "*response*.json",
    "*response*.jsonl",
    "*session*.json",
    "*session*.jsonl",
    "*usage*.json",
    "*usage*.jsonl",
    "data/**/*.json",
    "data/**/*.jsonl",
    "export*/**/*.json",
    "export*/**/*.jsonl",
    "history/**/*.json",
    "history/**/*.jsonl",
    "log/**/*.json",
    "log/**/*.jsonl",
    "logs/**/*.json",
    "logs/**/*.jsonl",
    "session/**/*.json",
    "session/**/*.jsonl",
    "sessions/**/*.json",
    "sessions/**/*.jsonl",
    "telemetry/**/*.json",
    "telemetry/**/*.jsonl",
    "trace*/**/*.json",
    "trace*/**/*.jsonl",
)
_MAX_DISCOVERED_FILES = 200


def _flatten_candidates(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class GenericOpenAICompatibleAdapter(BaseAdapter):
    source_id = "generic-openai-compatible"
    display_name = "Generic API Compatible"
    provider = "api-compatible"
    accuracy_level = "exact"
    parser_version = "generic-api-compatible-v2"

    def __init__(self) -> None:
        self.glob_env = TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
        self.discovery_root_env = TOKEN_USAGE_DISCOVERY_ROOTS_ENV
        self.cache = FileEventCache()

    def _resolve_explicit_paths(self) -> list[Path]:
        patterns = _flatten_candidates(os.environ.get(self.glob_env, ""))
        paths: list[Path] = []
        for pattern in patterns:
            matches = glob.glob(expand_path_text(pattern), recursive=True)
            paths.extend(Path(match) for match in matches)
        return sorted({path for path in paths if path.is_file()})

    def _resolve_discovery_roots(self) -> list[Path]:
        configured = _flatten_candidates(os.environ.get(self.discovery_root_env, ""))
        if configured:
            return [Path(expand_path_text(item)).expanduser() for item in configured]
        return default_discovery_roots()

    def _candidate_bases(self) -> list[Path]:
        configured = bool(_flatten_candidates(os.environ.get(self.discovery_root_env, "")))
        bases: list[Path] = []
        seen: set[Path] = set()
        for root in self._resolve_discovery_roots():
            if not root.exists() or not root.is_dir():
                continue
            if configured and root not in seen:
                bases.append(root)
                seen.add(root)
            try:
                children = list(root.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                lowered = child.name.lower()
                if any(keyword in lowered for keyword in _DISCOVERY_KEYWORDS) and child not in seen:
                    bases.append(child)
                    seen.add(child)
        return bases

    def _discover_paths(self) -> list[Path]:
        discovered: set[Path] = set()
        for base in self._candidate_bases():
            for pattern in _DISCOVERY_FILE_PATTERNS:
                try:
                    for match in base.glob(pattern):
                        if not match.is_file() or match.suffix not in {".json", ".jsonl"}:
                            continue
                        discovered.add(match)
                        if len(discovered) >= _MAX_DISCOVERED_FILES:
                            return sorted(discovered)
                except OSError:
                    continue
        return sorted(discovered)

    def _resolve_paths(self) -> list[Path]:
        explicit = self._resolve_explicit_paths()
        discovered = self._discover_paths()
        return sorted({*explicit, *discovered})

    def _path_has_exact_usage(self, path: Path) -> bool:
        try:
            for index, record in enumerate(self._iter_records(path)):
                usage = find_usage_dict(record)
                timestamp_value = find_first_value(record, TIMESTAMP_KEYS)
                if usage and timestamp_value and normalize_usage(usage)["total_tokens"] > 0:
                    return True
                if index >= 19:
                    break
        except (OSError, json.JSONDecodeError):
            return False
        return False

    def detect(self) -> SourceDetection:
        configured_paths = self._resolve_paths()
        ready_paths = [path for path in configured_paths if self._path_has_exact_usage(path)]
        if not configured_paths:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "no compatible usage logs found; set "
                    f"{self.glob_env} for exact files or {self.discovery_root_env} for custom search roots"
                ),
            )
        if not ready_paths:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "compatible logs were found, but none exposed exact usage payloads yet; "
                    f"set {self.glob_env} to point at token-bearing JSON/JSONL files if needed"
                ),
                candidate_paths=[str(path) for path in configured_paths[:2]],
            )

        has_explicit = bool(self._resolve_explicit_paths())
        summary = "configured API usage logs found" if has_explicit else "auto-discovered compatible API usage logs"
        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=True,
            summary=summary,
            candidate_paths=[str(path) for path in ready_paths[:2]],
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

    def _collect_file(self, path: Path, fallback_tz, pricing: PricingDatabase) -> tuple[list[UsageEvent], list[str]]:
        events: list[UsageEvent] = []
        verification_issues: list[str] = []

        try:
            for record in self._iter_records(path):
                usage = find_usage_dict(record)
                timestamp_value = find_first_value(record, TIMESTAMP_KEYS)
                if not usage or not timestamp_value:
                    continue
                usage_values = normalize_usage(usage)
                if usage_values["total_tokens"] <= 0:
                    continue
                timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                provider = str(find_first_value(record, PROVIDER_KEYS) or self.provider)
                raw_model = find_first_value(record, MODEL_KEYS)
                canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
                normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
                model_resolution = "unknown"
                if canonical_model:
                    model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"
                events.append(
                    UsageEvent(
                        source=self.source_id,
                        provider=provider,
                        timestamp=timestamp,
                        session_id=str(find_first_value(record, SESSION_KEYS) or path.stem),
                        project_path=find_first_value(record, PROJECT_KEYS),
                        model=canonical_model or raw_model,
                        input_tokens=usage_values["input_tokens"],
                        cached_input_tokens=usage_values["cached_input_tokens"],
                        output_tokens=usage_values["output_tokens"],
                        reasoning_tokens=usage_values["reasoning_tokens"],
                        total_tokens=usage_values["total_tokens"],
                        accuracy_level=self.accuracy_level,
                        raw_event_kind="generic_usage:delta",
                        source_path=str(path),
                        raw_model=str(raw_model) if raw_model not in (None, "") else None,
                        model_resolution=model_resolution,
                        model_source="generic_record" if raw_model not in (None, "") else None,
                    )
                )
        except (OSError, json.JSONDecodeError) as exc:
            verification_issues.append(f"failed parsing {path}: {exc}")

        return events, verification_issues

    def _load_or_parse_file(
        self,
        path: Path,
        *,
        fallback_tz,
        pricing: PricingDatabase,
    ) -> tuple[list[UsageEvent], list[str]]:
        cached = self.cache.load(
            source_id=self.source_id,
            parser_version=self.parser_version,
            path=path,
        )
        if cached is not None:
            return cached

        file_events, file_issues = self._collect_file(path, fallback_tz, pricing)
        self.cache.save(
            source_id=self.source_id,
            parser_version=self.parser_version,
            path=path,
            events=file_events,
            verification_issues=file_issues,
        )
        return file_events, file_issues

    def _load_or_build_day_rollups(
        self,
        path: Path,
        *,
        fallback_tz,
        pricing: PricingDatabase,
        timezone_name: str,
    ) -> tuple[list[UsageEvent], list[str]]:
        cached = self.cache.load_day_rollups(
            source_id=self.source_id,
            parser_version=self.parser_version,
            path=path,
            timezone_name=timezone_name,
        )
        if cached is not None:
            return cached

        file_events, file_issues = self._load_or_parse_file(path, fallback_tz=fallback_tz, pricing=pricing)
        rollups = build_day_rollups(file_events, tz_name=timezone_name)
        self.cache.save_day_rollups(
            source_id=self.source_id,
            parser_version=self.parser_version,
            path=path,
            timezone_name=timezone_name,
            events=rollups,
            verification_issues=file_issues,
        )
        return rollups, file_issues

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(detection=detection, skipped_reasons=[detection.summary])

        paths = self._resolve_paths()
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in paths:
            file_events, file_issues = self._load_or_parse_file(path, fallback_tz=fallback_tz, pricing=pricing)
            events.extend(event for event in file_events if within_window(window, event.timestamp))
            verification_issues.extend(file_issues)

        if not events:
            verification_issues.append("no exact usage records found in compatible API logs")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(paths),
            verification_issues=verification_issues[:10],
        )

    def collect_chart(self, window) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(detection=detection, skipped_reasons=[detection.summary])

        full_days, partial_days = split_window_days(window)
        if not full_days:
            return self.collect(window)

        paths = self._resolve_paths()
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in paths:
            rollups, rollup_issues = self._load_or_build_day_rollups(
                path,
                fallback_tz=fallback_tz,
                pricing=pricing,
                timezone_name=window.timezone_name,
            )
            rollup_days = {day_key(event.timestamp, tz_name=window.timezone_name) for event in rollups}
            events.extend(
                event
                for event in rollups
                if day_key(event.timestamp, tz_name=window.timezone_name) in full_days
            )
            verification_issues.extend(rollup_issues)

            if not (rollup_days & partial_days):
                continue

            file_events, file_issues = self._load_or_parse_file(path, fallback_tz=fallback_tz, pricing=pricing)
            events.extend(
                event
                for event in file_events
                if within_window(window, event.timestamp)
                and day_key(event.timestamp, tz_name=window.timezone_name) in partial_days
            )
            verification_issues.extend(file_issues)

        if not events:
            verification_issues.append("no exact usage records found in compatible API logs")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(paths),
            verification_issues=verification_issues[:10],
        )
