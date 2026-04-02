from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from adapters.base import BaseAdapter
from core.chromium_cache import ChromiumCacheJsonEntry, iter_json_entries
from core.config import default_desktop_app_roots, expand_path_text
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


_MAX_DETECTION_ENTRIES = 120
_IGNORED_URL_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".js",
    ".css",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
)


def _flatten_env_paths(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


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
    if not parsed.scheme or not parsed.netloc:
        return url
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _matches_url_keywords(url: str, keywords: tuple[str, ...]) -> bool:
    lowered_url = url.lower()
    return any(keyword.lower() in lowered_url for keyword in keywords)


@dataclass(frozen=True)
class ChromiumDesktopSourceDefinition:
    source_id: str
    display_name: str
    provider: str
    env_name: str
    app_names: tuple[str, ...]
    response_url_keywords: tuple[str, ...]
    usage_url_keywords: tuple[str, ...] = ()
    accuracy_level: str = "exact"


class ChromiumDesktopAdapter(BaseAdapter):
    parser_version = "chromium-desktop-v1"

    def __init__(
        self,
        definition: ChromiumDesktopSourceDefinition,
        *,
        root: Path | None = None,
    ) -> None:
        self.definition = definition
        self.source_id = definition.source_id
        self.display_name = definition.display_name
        self.provider = definition.provider
        self.accuracy_level = definition.accuracy_level
        self.root = root
        self._inventory: dict[str, object] | None = None

    def _candidate_roots(self) -> list[Path]:
        if self.root is not None:
            return [self.root]

        raw_value = os.environ.get(self.definition.env_name, "").strip()
        if raw_value:
            return [Path(expand_path_text(item)).expanduser() for item in _flatten_env_paths(raw_value)]

        return default_desktop_app_roots(self.definition.app_names)

    def _existing_roots(self) -> list[Path]:
        return [path for path in self._candidate_roots() if path.exists()]

    def _cache_dir(self, root: Path) -> Path:
        return root / "Cache" / "Cache_Data"

    def _indexeddb_dir(self, root: Path) -> Path:
        return root / "IndexedDB"

    def _local_storage_dir(self, root: Path) -> Path:
        return root / "Local Storage"

    def _cache_files(self, root: Path) -> list[Path]:
        cache_dir = self._cache_dir(root)
        if not cache_dir.exists() or not cache_dir.is_dir():
            return []
        return sorted(path for path in cache_dir.iterdir() if path.is_file())

    def _indexeddb_files(self, root: Path) -> list[Path]:
        indexeddb_dir = self._indexeddb_dir(root)
        if not indexeddb_dir.exists() or not indexeddb_dir.is_dir():
            return []
        matches: list[Path] = []
        for pattern in ("*.log", "*.ldb"):
            matches.extend(path for path in indexeddb_dir.rglob(pattern) if path.is_file())
        return sorted({path for path in matches})

    def _local_storage_files(self, root: Path) -> list[Path]:
        local_storage_dir = self._local_storage_dir(root)
        if not local_storage_dir.exists() or not local_storage_dir.is_dir():
            return []
        matches: list[Path] = []
        for pattern in ("*.log", "*.ldb"):
            matches.extend(path for path in local_storage_dir.rglob(pattern) if path.is_file())
        return sorted({path for path in matches})

    def _is_known_response_url(self, url: str) -> bool:
        if not _matches_url_keywords(url, self.definition.response_url_keywords):
            return False
        path = urlparse(url).path.lower()
        return not any(path.endswith(suffix) for suffix in _IGNORED_URL_SUFFIXES)

    def _is_usage_url(self, url: str) -> bool:
        if not self.definition.usage_url_keywords:
            return self._is_known_response_url(url)
        return _matches_url_keywords(url, self.definition.usage_url_keywords)

    def _fallback_model_from_entry(self, entry: ChromiumCacheJsonEntry, carrier) -> str | None:  # pragma: no cover - hook
        return None

    def _build_inventory(self) -> dict[str, object]:
        if self._inventory is not None:
            return self._inventory

        roots = self._existing_roots()
        cache_files: list[Path] = []
        decoded_entries: list[ChromiumCacheJsonEntry] = []
        usage_entries: list[ChromiumCacheJsonEntry] = []
        sample_urls: list[str] = []
        indexeddb_files: list[Path] = []
        local_storage_files: list[Path] = []

        for root in roots:
            cache_files.extend(self._cache_files(root))
            indexeddb_files.extend(self._indexeddb_files(root))
            local_storage_files.extend(self._local_storage_files(root))
            cache_dir = self._cache_dir(root)
            if not cache_dir.exists():
                continue

            for entry in iter_json_entries(
                cache_dir,
                url_keywords=self.definition.response_url_keywords,
                max_files=_MAX_DETECTION_ENTRIES,
            ):
                if not self._is_known_response_url(entry.url):
                    continue
                decoded_entries.append(entry)
                redacted_url = _redact_url(entry.url)
                if len(sample_urls) < 3 and redacted_url not in sample_urls:
                    sample_urls.append(redacted_url)

                if not self._is_usage_url(entry.url):
                    continue

                found_usage = False
                for _, usage in iter_usage_carriers(entry.payload):
                    if normalize_usage(usage)["total_tokens"] > 0:
                        found_usage = True
                        break
                if found_usage:
                    usage_entries.append(entry)

        self._inventory = {
            "roots": roots,
            "cache_files": sorted({path for path in cache_files}),
            "decoded_entries": decoded_entries,
            "usage_entries": usage_entries,
            "sample_urls": sample_urls,
            "indexeddb_files": sorted({path for path in indexeddb_files}),
            "local_storage_files": sorted({path for path in local_storage_files}),
        }
        return self._inventory

    def detect(self) -> SourceDetection:
        candidate_roots = self._candidate_roots()
        existing_roots = self._existing_roots()
        if not existing_roots:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    f"{self.display_name} desktop data directory not found; "
                    f"set {self.definition.env_name} if the app stores data elsewhere"
                ),
                candidate_paths=[str(path) for path in candidate_roots[:3]],
            )

        inventory = self._build_inventory()
        cache_files = list(inventory["cache_files"])
        decoded_entries = list(inventory["decoded_entries"])
        usage_entries = list(inventory["usage_entries"])
        sample_urls = list(inventory["sample_urls"])
        indexeddb_files = list(inventory["indexeddb_files"])
        local_storage_files = list(inventory["local_storage_files"])

        if not cache_files and not indexeddb_files and not local_storage_files:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    f"{self.display_name} data directory exists, but no Chromium/Electron stores were found yet; "
                    f"set {self.definition.env_name} if needed"
                ),
                candidate_paths=[str(path) for path in existing_roots[:3]],
            )

        details = [
            f"inspected {len(cache_files)} cache file(s) across {len(existing_roots)} desktop root(s)",
            f"decoded {len(decoded_entries)} API JSON response(s) from Chromium Cache_Data",
        ]
        if indexeddb_files:
            details.append(f"found {len(indexeddb_files)} IndexedDB LevelDB file(s)")
        if local_storage_files:
            details.append(f"found {len(local_storage_files)} Local Storage LevelDB file(s)")
        if sample_urls:
            details.append("sample endpoints: " + "; ".join(sample_urls))

        if usage_entries:
            details.append(f"exact token payloads were recovered from cached {self.display_name} API responses")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary=f"decoded {self.display_name} desktop API cache entries with exact usage payloads",
                candidate_paths=[str(entry.path) for entry in usage_entries[:2]],
                details=details,
            )

        if decoded_entries or indexeddb_files or local_storage_files:
            details.append(
                "desktop traces were detected successfully, but the current snapshot did not expose exact token-bearing responses"
            )
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    f"{self.display_name} desktop traces detected, but no exact token payloads were present in the current snapshot"
                ),
                candidate_paths=[str(path) for path in [*existing_roots[:1], *cache_files[:1], *indexeddb_files[:1]][:3]],
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
                f"{self.display_name} cache directory exists, but no matching API JSON responses were decoded yet"
            ),
            candidate_paths=[str(path) for path in [*existing_roots[:1], *candidate_roots[:2]][:3]],
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
                    [f"decoded {self.display_name} desktop responses, but none exposed exact usage fields"]
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
        seen: set[tuple[str, str, str, int, int]] = set()
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
                        verification_issues.append(f"invalid timestamp in {self.display_name} cache {entry.path}: {exc}")
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
                raw_model = (
                    find_first_value(carrier, MODEL_KEYS)
                    or find_first_value(entry.payload, MODEL_KEYS)
                    or self._fallback_model_from_entry(entry, carrier)
                )
                canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
                normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
                model_resolution = "unknown"
                if canonical_model:
                    model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

                session_id = str(
                    find_first_value(carrier, SESSION_KEYS)
                    or find_first_value(entry.payload, SESSION_KEYS)
                    or _resolve_url_session_id(entry.url)
                    or entry.path.stem
                )
                dedupe_key = (
                    session_id,
                    canonical_model or str(raw_model or ""),
                    str(entry.path),
                    usage_values["total_tokens"],
                    int(timestamp.timestamp()),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                events.append(
                    UsageEvent(
                        source=self.source_id,
                        provider=provider,
                        timestamp=timestamp,
                        session_id=session_id,
                        project_path=find_first_value(carrier, PROJECT_KEYS) or find_first_value(entry.payload, PROJECT_KEYS),
                        model=canonical_model or (str(raw_model) if raw_model not in (None, "") else None),
                        input_tokens=usage_values["input_tokens"],
                        cached_input_tokens=usage_values["cached_input_tokens"],
                        output_tokens=usage_values["output_tokens"],
                        reasoning_tokens=usage_values["reasoning_tokens"],
                        total_tokens=usage_values["total_tokens"],
                        accuracy_level=self.accuracy_level,
                        raw_event_kind="chromium_desktop:cache_usage",
                        source_path=str(entry.path),
                        raw_model=str(raw_model) if raw_model not in (None, "") else None,
                        model_resolution=model_resolution,
                        model_source="desktop_cache_record" if raw_model not in (None, "") else None,
                    )
                )

        if used_cache_timestamp:
            verification_issues.append(
                f"some {self.display_name} cache responses lacked server timestamps, so file modification time was used as a fallback"
            )
        if not events:
            verification_issues.append(f"no {self.display_name} usage events landed inside the selected time window")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(decoded_entries),
            verification_issues=verification_issues[:10],
        )
