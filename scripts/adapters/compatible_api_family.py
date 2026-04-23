from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
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
URL_KEYS = (
    "url",
    "request_url",
    "requestUrl",
    "endpoint",
    "api_base",
    "apiBase",
    "base_url",
    "baseUrl",
    "origin",
    "host",
    "domain",
)


@dataclass(frozen=True)
class ProviderSourceDefinition:
    source_id: str
    display_name: str
    provider: str
    provider_aliases: tuple[str, ...]
    model_aliases: tuple[str, ...] = ()
    endpoint_aliases: tuple[str, ...] = ()
    discovery_keywords: tuple[str, ...] = ()


TOP_PROVIDER_SOURCE_DEFINITIONS: tuple[ProviderSourceDefinition, ...] = (
    ProviderSourceDefinition("openai-api", "OpenAI API", "openai", ("openai",), ("gpt-4", "gpt-5", "o1", "o3", "o4")),
    ProviderSourceDefinition("anthropic-api", "Anthropic API", "anthropic", ("anthropic", "claude"), ("claude",)),
    ProviderSourceDefinition("google-gemini-api", "Google Gemini API", "google", ("google", "gemini", "vertex-ai"), ("gemini",)),
    ProviderSourceDefinition("moonshot-kimi-api", "Moonshot Kimi API", "moonshotai", ("moonshot", "moonshotai", "kimi"), ("kimi",)),
    ProviderSourceDefinition("zhipu-glm-api", "Zhipu GLM API", "z-ai", ("zhipu", "z-ai", "bigmodel", "glm"), ("glm",)),
    ProviderSourceDefinition("qwen-api", "Qwen API", "qwen", ("qwen", "dashscope", "aliyun"), ("qwen",)),
    ProviderSourceDefinition("deepseek-api", "DeepSeek API", "deepseek", ("deepseek",), ("deepseek",)),
    ProviderSourceDefinition("minimax-api", "MiniMax API", "minimax", ("minimax",), ("minimax", "abab")),
    ProviderSourceDefinition("xai-grok-api", "xAI Grok API", "xai", ("xai", "grok"), ("grok",)),
    ProviderSourceDefinition("cohere-api", "Cohere API", "cohere", ("cohere",), ("command-r", "command-a", "aya")),
    ProviderSourceDefinition("mistral-api", "Mistral API", "mistral", ("mistral",), ("mistral", "mixtral", "codestral")),
    ProviderSourceDefinition("perplexity-api", "Perplexity API", "perplexity", ("perplexity", "sonar"), ("sonar",)),
    ProviderSourceDefinition("openrouter-api", "OpenRouter API", "openrouter", ("openrouter",), ("openrouter",)),
    ProviderSourceDefinition("togetherai-api", "Together AI API", "togetherai", ("together", "togetherai"), ("together",)),
    ProviderSourceDefinition("fireworks-api", "Fireworks API", "fireworks", ("fireworks", "fireworks-ai"), ("fireworks",)),
    ProviderSourceDefinition("azure-openai-api", "Azure OpenAI API", "azure-openai", ("azure-openai", "azure", "azureai"), ("azure-openai",)),
    ProviderSourceDefinition("baidu-qianfan-api", "Baidu Qianfan API", "baidu", ("baidu", "qianfan", "wenxin", "ernie"), ("ernie",)),
    ProviderSourceDefinition("tencent-hunyuan-api", "Tencent Hunyuan API", "tencent", ("tencent", "hunyuan"), ("hunyuan",)),
    ProviderSourceDefinition("stepfun-api", "StepFun API", "stepfun", ("stepfun", "step"), ("step-", "stepfun")),
    ProviderSourceDefinition("doubao-api", "Doubao API", "bytedance", ("bytedance", "doubao", "volcengine"), ("doubao",)),
    ProviderSourceDefinition(
        "sensenova-api",
        "SenseNova API",
        "sensenova",
        ("sensenova", "sensechat", "sensetime", "日日新"),
        ("sensechat", "sensenova"),
        ("api.sensenova.cn", "sensenova.cn"),
        ("sensenova", "sensechat", "sensetime"),
    ),
    ProviderSourceDefinition(
        "baichuan-api",
        "Baichuan API",
        "baichuan",
        ("baichuan", "baichuan-ai", "baichuanai"),
        ("baichuan",),
        ("baichuan-ai.com",),
        ("baichuan",),
    ),
    ProviderSourceDefinition(
        "siliconflow-api",
        "SiliconFlow API",
        "siliconflow",
        ("siliconflow", "siliconcloud"),
        (),
        ("api.siliconflow.cn", "siliconflow.cn"),
        ("siliconflow", "siliconcloud"),
    ),
    ProviderSourceDefinition(
        "spark-api",
        "Spark API",
        "spark",
        ("spark", "xinghuo", "xfyun", "sparkdesk"),
        ("spark", "xinghuo"),
        (
            "spark-api-open.xf-yun.com",
            "spark-api.xf-yun.com",
            "sparkcube-api.xf-yun.com",
            "xf-yun.com",
        ),
        ("spark", "xinghuo", "xfyun"),
    ),
)


def _flatten_candidates(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _normalize_hint(value) -> str:
    if value in (None, ""):
        return ""
    normalized = str(value).strip().lower().replace("\\", "/")
    return normalized.replace("_", "-")


def _matches_alias(normalized: str, aliases: tuple[str, ...]) -> bool:
    if not normalized:
        return False
    for alias in aliases:
        candidate = _normalize_hint(alias)
        if not candidate:
            continue
        if normalized == candidate:
            return True
        if normalized.startswith(candidate + "/") or normalized.startswith(candidate + "-"):
            return True
        if "/" in normalized and candidate == normalized.split("/")[-1]:
            return True
        if candidate in normalized and any(sep in normalized for sep in ("-", "/", ".")):
            return True
    return False


def _definition_matches_record(definition: ProviderSourceDefinition, record) -> bool:
    provider_hint = _normalize_hint(find_first_value(record, PROVIDER_KEYS))
    if provider_hint:
        if _matches_alias(provider_hint, definition.provider_aliases):
            return True
        return False

    endpoint_hint = _normalize_hint(find_first_value(record, URL_KEYS))
    if endpoint_hint and _matches_alias(endpoint_hint, definition.endpoint_aliases):
        return True

    raw_model = _normalize_hint(find_first_value(record, MODEL_KEYS))
    return _matches_alias(raw_model, definition.model_aliases or definition.provider_aliases)


def _all_known_definition_aliases() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    provider_aliases = tuple(alias for definition in TOP_PROVIDER_SOURCE_DEFINITIONS for alias in definition.provider_aliases)
    model_aliases = tuple(alias for definition in TOP_PROVIDER_SOURCE_DEFINITIONS for alias in definition.model_aliases)
    endpoint_aliases = tuple(alias for definition in TOP_PROVIDER_SOURCE_DEFINITIONS for alias in definition.endpoint_aliases)
    return provider_aliases, model_aliases, endpoint_aliases


class CompatibleApiAdapter(BaseAdapter):
    accuracy_level = "exact"
    parser_version = "compatible-api-v1"

    def __init__(
        self,
        *,
        source_id: str,
        display_name: str,
        provider: str,
        discovery_keywords: tuple[str, ...] = (),
        exclude_known_providers: bool = False,
        definition: ProviderSourceDefinition | None = None,
    ) -> None:
        self.source_id = source_id
        self.display_name = display_name
        self.provider = provider
        self.definition = definition
        self.exclude_known_providers = exclude_known_providers
        self.discovery_keywords = tuple(dict.fromkeys(keyword for keyword in discovery_keywords if keyword))
        self.glob_env = TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
        self.discovery_root_env = TOKEN_USAGE_DISCOVERY_ROOTS_ENV
        self.cache = FileEventCache()
        self.parser_version = f"compatible-api-v3:{self.source_id}"
        (
            self._known_provider_aliases,
            self._known_model_aliases,
            self._known_endpoint_aliases,
        ) = _all_known_definition_aliases()

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
                if any(keyword in lowered for keyword in self.discovery_keywords) and child not in seen:
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

    def _record_matches_source(self, record) -> bool:
        if self.definition is not None:
            return _definition_matches_record(self.definition, record)

        if not self.exclude_known_providers:
            return True

        provider_hint = _normalize_hint(find_first_value(record, PROVIDER_KEYS))
        if provider_hint and _matches_alias(provider_hint, self._known_provider_aliases):
            return False

        endpoint_hint = _normalize_hint(find_first_value(record, URL_KEYS))
        if endpoint_hint and _matches_alias(endpoint_hint, self._known_endpoint_aliases):
            return False

        raw_model = _normalize_hint(find_first_value(record, MODEL_KEYS))
        if raw_model and _matches_alias(raw_model, self._known_model_aliases):
            return False
        return True

    def _path_has_exact_usage(self, path: Path) -> bool:
        try:
            for index, record in enumerate(self._iter_records(path)):
                if not self._record_matches_source(record):
                    if index >= 19:
                        break
                    continue
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
        source_phrase = self.display_name
        if not configured_paths:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    f"no {source_phrase} exact logs found; set {self.glob_env} for exact files or "
                    f"{self.discovery_root_env} for custom search roots"
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
                summary=f"compatible logs were found, but none exposed exact {source_phrase} usage payloads yet",
                candidate_paths=[str(path) for path in configured_paths[:2]],
            )

        has_explicit = bool(self._resolve_explicit_paths())
        summary = f"configured {source_phrase} exact logs found" if has_explicit else f"auto-discovered {source_phrase} exact logs"
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
                if not self._record_matches_source(record):
                    continue
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
                        raw_event_kind="compatible_api:delta",
                        source_path=str(path),
                        raw_model=str(raw_model) if raw_model not in (None, "") else None,
                        model_resolution=model_resolution,
                        model_source="compatible_api_record" if raw_model not in (None, "") else None,
                    )
                )
        except (OSError, json.JSONDecodeError) as exc:
            verification_issues.append(f"failed parsing {path}: {exc}")

        return events, verification_issues

    def _load_or_parse_file(self, path: Path, *, fallback_tz, pricing: PricingDatabase) -> tuple[list[UsageEvent], list[str]]:
        cached = self.cache.load(source_id=self.source_id, parser_version=self.parser_version, path=path)
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
        fallback_tz = window.start.tzinfo if window.start else __import__("datetime").datetime.now().astimezone().tzinfo

        for path in paths:
            file_events, file_issues = self._load_or_parse_file(path, fallback_tz=fallback_tz, pricing=pricing)
            events.extend(event for event in file_events if within_window(window, event.timestamp))
            verification_issues.extend(file_issues)

        if not events:
            verification_issues.append(f"no exact usage records found for {self.display_name}")

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
        fallback_tz = window.start.tzinfo if window.start else __import__("datetime").datetime.now().astimezone().tzinfo

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
            verification_issues.append(f"no exact usage records found for {self.display_name}")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(paths),
            verification_issues=verification_issues[:10],
        )


class GenericOpenAICompatibleAdapter(CompatibleApiAdapter):
    # v1.2 slim: per-provider adapters (qwen-api, zhipu-glm-api, ...) were
    # archived because the deployment routes everything through a single
    # 百炼 compatible URL. Generic is now the primary catcher for
    # ingress-companion JSONL and TOKEN_USAGE_GENERIC_LOG_GLOBS output,
    # so it must be in the default rollup (was False previously to avoid
    # double-counting with per-provider family).
    default_selected = True

    def __init__(self) -> None:
        super().__init__(
            source_id="generic-openai-compatible",
            display_name="Generic API Compatible",
            provider="api-compatible",
            discovery_keywords=(
                "anthropic",
                "bigmodel",
                "dashscope",
                "deepseek",
                "gemini",
                "glm",
                "helicone",
                "kimi",
                "langfuse",
                "litellm",
                "llm",
                "minimax",
                "moonshot",
                "openai",
                "openrouter",
                "opencode",
                "qwen",
                "zhipu",
            ),
        )


def build_provider_api_adapters() -> list[CompatibleApiAdapter]:
    adapters: list[CompatibleApiAdapter] = []
    for definition in TOP_PROVIDER_SOURCE_DEFINITIONS:
        keywords = tuple(dict.fromkeys((*definition.provider_aliases, *definition.model_aliases, *definition.discovery_keywords)))
        adapters.append(
            CompatibleApiAdapter(
                source_id=definition.source_id,
                display_name=definition.display_name,
                provider=definition.provider,
                discovery_keywords=keywords,
                definition=definition,
            )
        )
    return adapters
