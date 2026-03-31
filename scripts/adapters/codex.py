from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from adapters.base import BaseAdapter
from core.day_rollup import build_day_rollups, day_key, split_window_days
from core.config import TOKEN_USAGE_CODEX_ROOT_ENV, resolve_path_override
from core.file_cache import FileEventCache
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.pricing import PricingDatabase
from core.time_window import parse_timestamp, within_window


_MODEL_TEXT_RE = re.compile(r"\b(GPT-\d+(?:\.\d+)?(?:-Codex)?)\b", re.IGNORECASE)
_GENERIC_GPT5_RE = re.compile(r"\bGPT-5\b", re.IGNORECASE)
_GPT54_ROLLOUT_DATE = date(2026, 3, 5)
_MODEL_RESOLUTION_RANK = {
    "unknown": 0,
    "alias": 1,
    "inferred": 2,
    "exact": 3,
}


def _normalize_usage(payload: dict[str, object]) -> dict[str, int]:
    input_tokens = int(payload.get("input_tokens", 0) or 0)
    cached_input_tokens = int(payload.get("cached_input_tokens", 0) or 0)
    output_tokens = int(payload.get("output_tokens", 0) or 0)
    reasoning_tokens = int(
        payload.get("reasoning_output_tokens", payload.get("reasoning_tokens", 0)) or 0
    )
    total_tokens = int(payload.get("total_tokens", input_tokens + output_tokens) or 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def _subtract_usage(current: dict[str, int], previous: dict[str, int]) -> dict[str, int]:
    return {key: current[key] - previous[key] for key in current}


def _codex_event_usage(usage: dict[str, int]) -> dict[str, int]:
    input_total = int(usage.get("input_tokens", 0) or 0)
    cached_input_tokens = int(usage.get("cached_input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning_tokens = int(usage.get("reasoning_tokens", 0) or 0)
    input_tokens = max(0, input_total - cached_input_tokens)
    total_tokens = input_tokens + cached_input_tokens + output_tokens + reasoning_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def _infer_model_name(payload: dict[str, object]) -> str | None:
    explicit_model = payload.get("model") or payload.get("model_name")
    if explicit_model:
        return str(explicit_model)

    base_instructions = payload.get("base_instructions")
    if isinstance(base_instructions, dict):
        text = base_instructions.get("text")
        if isinstance(text, str):
            match = _MODEL_TEXT_RE.search(text)
            if match:
                return match.group(1)
            if _GENERIC_GPT5_RE.search(text):
                return "GPT-5"

    return None


def _parse_record_timestamp(record: dict[str, object], fallback_tz) -> datetime | None:
    timestamp_value = record.get("timestamp")
    if timestamp_value in (None, ""):
        return None
    try:
        return parse_timestamp(str(timestamp_value), fallback_tz)
    except (TypeError, ValueError):
        return None


def _codex_release_model(session_started_at: datetime | None) -> str | None:
    if not session_started_at:
        return None
    if session_started_at.date() >= _GPT54_ROLLOUT_DATE:
        return "gpt-5.4"
    return "gpt-5.3-codex"


def _resolve_model_info(
    raw_model: str | None,
    *,
    provider: str | None,
    pricing: PricingDatabase,
    session_started_at: datetime | None,
    source: str,
) -> dict[str, object]:
    raw_value = str(raw_model).strip() if raw_model not in (None, "") else None
    if raw_value:
        normalized = pricing.normalize_model_name(raw_value)
        if normalized == "gpt-5":
            inferred_model = _codex_release_model(session_started_at)
            if inferred_model:
                return {
                    "model": inferred_model,
                    "raw_model": raw_value,
                    "model_resolution": "inferred",
                    "model_source": source,
                }

        canonical = pricing.canonical_model(raw_value, provider) or normalized or raw_value
        resolution = "exact" if canonical == normalized else "alias"
        return {
            "model": canonical,
            "raw_model": raw_value,
            "model_resolution": resolution,
            "model_source": source,
        }

    inferred_model = _codex_release_model(session_started_at)
    if inferred_model:
        return {
            "model": inferred_model,
            "raw_model": None,
            "model_resolution": "inferred",
            "model_source": "codex_release_inference",
        }

    return {
        "model": None,
        "raw_model": None,
        "model_resolution": "unknown",
        "model_source": None,
    }


def _prefer_model_info(current: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    if not candidate.get("model"):
        return current
    if not current.get("model"):
        return candidate

    current_rank = _MODEL_RESOLUTION_RANK.get(str(current.get("model_resolution")), 0)
    candidate_rank = _MODEL_RESOLUTION_RANK.get(str(candidate.get("model_resolution")), 0)
    if candidate_rank > current_rank:
        return candidate
    if candidate_rank == current_rank and candidate.get("model_source") == "turn_context":
        return candidate
    return current


class CodexAdapter(BaseAdapter):
    source_id = "codex"
    display_name = "Codex"
    provider = "openai"
    accuracy_level = "exact"
    parser_version = "codex-v1"

    def __init__(self) -> None:
        self.root = resolve_path_override(
            TOKEN_USAGE_CODEX_ROOT_ENV,
            Path.home() / ".codex" / "sessions",
        )
        self.cache = FileEventCache()

    def detect(self) -> SourceDetection:
        if not self.root.exists():
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=f"session directory not found; set {TOKEN_USAGE_CODEX_ROOT_ENV} if logs live elsewhere",
                candidate_paths=[str(self.root)],
            )

        sample = sorted(str(path) for path in self.root.rglob("*.jsonl"))[:2]
        if not sample:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=f"no session jsonl files found under {self.root}; check {TOKEN_USAGE_CODEX_ROOT_ENV}",
                candidate_paths=[str(self.root)],
            )

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=True,
            summary="local token_count logs available",
            candidate_paths=sample,
        )

    def _scan_files(self, window) -> list[Path]:
        if window.start and window.end:
            tzinfo = window.start.tzinfo or window.end.tzinfo
            start_day = window.start.astimezone(tzinfo).date() - timedelta(days=1)
            end_day = window.end.astimezone(tzinfo).date()
            dated_paths: list[Path] = []
            cursor = start_day
            while cursor <= end_day:
                day_dir = self.root / f"{cursor.year:04d}" / f"{cursor.month:02d}" / f"{cursor.day:02d}"
                if day_dir.exists():
                    dated_paths.extend(sorted(day_dir.glob("*.jsonl")))
                cursor += timedelta(days=1)
            if dated_paths:
                return sorted({path for path in dated_paths if path.is_file()})

        return sorted(self.root.rglob("*.jsonl"))

    def _collect_file(self, path: Path, fallback_tz, pricing: PricingDatabase) -> tuple[list[UsageEvent], list[str]]:
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        session_id = path.stem
        project_path = None
        provider = self.provider
        session_started_at: datetime | None = None
        model_info = {
            "model": None,
            "raw_model": None,
            "model_resolution": "unknown",
            "model_source": None,
        }
        previous_total: dict[str, int] | None = None

        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError:
                        verification_issues.append(f"invalid json ignored in {path}")
                        continue

                    record_type = record.get("type")
                    payload = record.get("payload", {})
                    record_timestamp = _parse_record_timestamp(record, fallback_tz)
                    if record_type == "session_meta":
                        session_id = payload.get("id") or session_id
                        project_path = payload.get("cwd") or project_path
                        provider = payload.get("model_provider") or provider
                        meta_timestamp = payload.get("timestamp") or record.get("timestamp")
                        if meta_timestamp not in (None, ""):
                            try:
                                session_started_at = parse_timestamp(str(meta_timestamp), fallback_tz)
                            except (TypeError, ValueError):
                                session_started_at = record_timestamp or session_started_at
                        elif record_timestamp:
                            session_started_at = record_timestamp or session_started_at

                        model_info = _prefer_model_info(
                            model_info,
                            _resolve_model_info(
                                _infer_model_name(payload),
                                provider=provider,
                                pricing=pricing,
                                session_started_at=session_started_at,
                                source="session_meta",
                            ),
                        )
                        continue

                    if record_type == "turn_context":
                        project_path = payload.get("cwd") or project_path
                        model_info = _prefer_model_info(
                            model_info,
                            _resolve_model_info(
                                payload.get("model"),
                                provider=provider,
                                pricing=pricing,
                                session_started_at=session_started_at or record_timestamp,
                                source="turn_context",
                            ),
                        )
                        continue

                    if record_type != "event_msg" or payload.get("type") != "token_count":
                        continue

                    info = payload.get("info")
                    if not isinstance(info, dict):
                        continue

                    event_model_info = model_info
                    payload_model = payload.get("model") or payload.get("model_name")
                    if payload_model not in (None, ""):
                        event_model_info = _prefer_model_info(
                            model_info,
                            _resolve_model_info(
                                str(payload_model),
                                provider=provider,
                                pricing=pricing,
                                session_started_at=session_started_at or record_timestamp,
                                source="token_count",
                            ),
                        )

                    last_usage = info.get("last_token_usage")
                    total_usage = info.get("total_token_usage")
                    delta_usage: dict[str, int] | None = None

                    if isinstance(last_usage, dict):
                        delta_usage = _normalize_usage(last_usage)
                        if isinstance(total_usage, dict):
                            previous_total = _normalize_usage(total_usage)
                    elif isinstance(total_usage, dict):
                        current_total = _normalize_usage(total_usage)
                        if previous_total is None:
                            delta_usage = current_total
                        else:
                            if current_total == previous_total:
                                continue
                            delta_usage = _subtract_usage(current_total, previous_total)
                            if min(delta_usage.values()) < 0:
                                verification_issues.append(f"negative total delta skipped in {path}")
                                previous_total = current_total
                                continue
                        previous_total = current_total
                    else:
                        continue

                    event_usage = _codex_event_usage(delta_usage)
                    timestamp = parse_timestamp(record["timestamp"], fallback_tz)
                    events.append(
                        UsageEvent(
                            source=self.source_id,
                            provider=provider,
                            timestamp=timestamp,
                            session_id=str(session_id),
                            project_path=project_path,
                            model=str(event_model_info.get("model")) if event_model_info.get("model") else None,
                            input_tokens=event_usage["input_tokens"],
                            cached_input_tokens=event_usage["cached_input_tokens"],
                            output_tokens=event_usage["output_tokens"],
                            reasoning_tokens=event_usage["reasoning_tokens"],
                            total_tokens=event_usage["total_tokens"],
                            accuracy_level=self.accuracy_level,
                            raw_event_kind="token_count:delta",
                            source_path=str(path),
                            raw_model=str(event_model_info.get("raw_model")) if event_model_info.get("raw_model") else None,
                            model_resolution=str(event_model_info.get("model_resolution") or "unknown"),
                            model_source=str(event_model_info.get("model_source")) if event_model_info.get("model_source") else None,
                        )
                    )
        except OSError as exc:
            verification_issues.append(f"failed reading {path}: {exc}")

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

        files = self._scan_files(window)
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in files:
            file_events, file_issues = self._load_or_parse_file(path, fallback_tz=fallback_tz, pricing=pricing)
            events.extend(event for event in file_events if within_window(window, event.timestamp))
            verification_issues.extend(file_issues)

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(files),
            verification_issues=verification_issues[:10],
        )

    def collect_chart(self, window) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(detection=detection, skipped_reasons=[detection.summary])

        full_days, partial_days = split_window_days(window)
        if not full_days:
            return self.collect(window)

        files = self._scan_files(window)
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        for path in files:
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

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(files),
            verification_issues=verification_issues[:10],
        )
