from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from adapters.base import BaseAdapter
from core.chromium_cache import ChromiumCacheJsonEntry, iter_json_entries
from core.config import (
    TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV,
    default_minimax_agent_root,
    resolve_path_override,
)
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
    iter_usage_carriers,
    normalize_usage,
)


_MINIMAX_URL_KEYWORDS = ("agent.minimax.io",)
_MAX_DETECTION_ENTRIES = 120


def _resolve_url_session_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("session_id", "sessionId", "conversation_id", "conversationId", "request_id", "requestId"):
        values = query.get(key)
        if values:
            return values[0]
    if parsed.path:
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[-1]
    return None


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _is_minimax_url(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return "agent.minimax.io" in netloc


class MiniMaxAgentAdapter(BaseAdapter):
    source_id = "minimax-agent"
    display_name = "MiniMax Agent"
    provider = "minimax"
    accuracy_level = "exact"
    parser_version = "minimax-agent-v1"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or resolve_path_override(
            TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV,
            default_minimax_agent_root(),
        )
        self.cache_dir = self.root / "Cache" / "Cache_Data"
        self._inventory: dict[str, object] | None = None

    def _cache_files(self) -> list[Path]:
        if not self.cache_dir.exists() or not self.cache_dir.is_dir():
            return []
        return sorted(path for path in self.cache_dir.iterdir() if path.is_file())

    def _build_inventory(self) -> dict[str, object]:
        if self._inventory is not None:
            return self._inventory

        cache_files = self._cache_files()
        decoded_entries = [
            entry
            for entry in iter_json_entries(
                self.cache_dir,
                url_keywords=_MINIMAX_URL_KEYWORDS,
                max_files=_MAX_DETECTION_ENTRIES,
            )
            if _is_minimax_url(entry.url)
        ]
        usage_entries: list[ChromiumCacheJsonEntry] = []
        sample_urls: list[str] = []

        for entry in decoded_entries:
            redacted_url = _redact_url(entry.url)
            if len(sample_urls) < 3 and redacted_url not in sample_urls:
                sample_urls.append(redacted_url)
            found_usage = False
            for _, usage in iter_usage_carriers(entry.payload):
                if normalize_usage(usage)["total_tokens"] > 0:
                    found_usage = True
                    break
            if found_usage:
                usage_entries.append(entry)

        self._inventory = {
            "cache_files": cache_files,
            "decoded_entries": decoded_entries,
            "usage_entries": usage_entries,
            "sample_urls": sample_urls,
        }
        return self._inventory

    def detect(self) -> SourceDetection:
        if not self.root.exists():
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "MiniMax Agent desktop data directory not found; "
                    f"set {TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV} if the app stores data elsewhere"
                ),
                candidate_paths=[str(self.root)],
            )

        if not self.cache_dir.exists():
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "MiniMax Agent data directory exists, but Chromium Cache_Data was not found yet; "
                    f"set {TOKEN_USAGE_MINIMAX_AGENT_ROOT_ENV} if needed"
                ),
                candidate_paths=[str(self.root), str(self.cache_dir)],
            )

        inventory = self._build_inventory()
        cache_files = list(inventory["cache_files"])
        decoded_entries = list(inventory["decoded_entries"])
        usage_entries = list(inventory["usage_entries"])
        sample_urls = list(inventory["sample_urls"])

        details = [
            f"inspected {len(cache_files)} cache file(s) under Chromium Cache_Data",
            f"decoded {len(decoded_entries)} JSON API response(s) for agent.minimax.io",
        ]
        if sample_urls:
            details.append("sample endpoints: " + "; ".join(sample_urls))

        if usage_entries:
            details.append("exact token payloads were recovered from cached MiniMax Agent API responses")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="decoded MiniMax Agent API cache entries with exact usage payloads",
                candidate_paths=[str(entry.path) for entry in usage_entries[:2]],
                details=details,
            )

        if decoded_entries:
            details.append("current cache snapshot decoded successfully, but only config/auth/session metadata endpoints were found")
            details.append("exact token collection depends on MiniMax Agent caching token-bearing chat/completion responses")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "MiniMax Agent desktop cache detected, but no exact token payloads were present in the current snapshot"
                ),
                candidate_paths=[str(self.cache_dir), *[str(entry.path) for entry in decoded_entries[:2]]][:3],
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
                "MiniMax Agent cache directory exists, but no JSON API responses for agent.minimax.io were decoded yet"
            ),
            candidate_paths=[str(self.cache_dir)],
            details=details,
        )

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        inventory = self._build_inventory()
        decoded_entries = list(inventory["decoded_entries"])
        usage_entries = list(inventory["usage_entries"])
        if not usage_entries:
            return SourceCollectResult(
                detection=detection,
                scanned_files=len(decoded_entries),
                verification_issues=(
                    ["decoded MiniMax Agent cache responses, but none exposed exact usage fields"]
                    if decoded_entries
                    else []
                ),
                skipped_reasons=[detection.summary],
            )

        pricing = PricingDatabase()
        fallback_tz = (
            window.start.tzinfo
            if window.start
            else __import__("datetime").datetime.now().astimezone().tzinfo
        )

        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        seen: set[tuple[str, str, str, int]] = set()
        used_cache_timestamp = False

        for entry in usage_entries:
            for carrier, usage in iter_usage_carriers(entry.payload):
                usage_values = normalize_usage(usage)
                if usage_values["total_tokens"] <= 0:
                    continue

                timestamp_value = find_first_value(carrier, TIMESTAMP_KEYS) or find_first_value(entry.payload, TIMESTAMP_KEYS)
                if timestamp_value not in (None, ""):
                    try:
                        timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                    except (TypeError, ValueError) as exc:
                        verification_issues.append(f"invalid timestamp in MiniMax cache {entry.path}: {exc}")
                        continue
                else:
                    timestamp = entry.captured_at
                    used_cache_timestamp = True

                if not within_window(window, timestamp):
                    continue

                provider = str(
                    find_first_value(carrier, PROVIDER_KEYS)
                    or find_first_value(entry.payload, PROVIDER_KEYS)
                    or self.provider
                )
                raw_model = find_first_value(carrier, MODEL_KEYS) or find_first_value(entry.payload, MODEL_KEYS)
                canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
                normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
                model_resolution = "unknown"
                if canonical_model:
                    model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

                session_id = (
                    find_first_value(carrier, SESSION_KEYS)
                    or find_first_value(entry.payload, SESSION_KEYS)
                    or _resolve_url_session_id(entry.url)
                    or entry.path.stem
                )
                dedupe_key = (str(session_id), timestamp.isoformat(), str(raw_model or canonical_model or ""), usage_values["total_tokens"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                events.append(
                    UsageEvent(
                        source=self.source_id,
                        provider=provider,
                        timestamp=timestamp,
                        session_id=str(session_id),
                        project_path=find_first_value(carrier, PROJECT_KEYS) or find_first_value(entry.payload, PROJECT_KEYS),
                        model=canonical_model or raw_model,
                        input_tokens=usage_values["input_tokens"],
                        cached_input_tokens=usage_values["cached_input_tokens"],
                        output_tokens=usage_values["output_tokens"],
                        reasoning_tokens=usage_values["reasoning_tokens"],
                        total_tokens=usage_values["total_tokens"],
                        accuracy_level=self.accuracy_level,
                        raw_event_kind=f"chromium_cache:{entry.body_encoding}",
                        source_path=str(entry.path),
                        raw_model=str(raw_model) if raw_model not in (None, "") else None,
                        model_resolution=model_resolution,
                        model_source="minimax_agent_cache" if raw_model not in (None, "") else None,
                    )
                )

        if used_cache_timestamp:
            verification_issues.append(
                "some MiniMax Agent cache responses lacked server timestamps, so file modification time was used as a fallback"
            )
        if not events and not verification_issues:
            verification_issues.append("no MiniMax Agent usage events landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(decoded_entries),
            verification_issues=verification_issues[:10],
        )
