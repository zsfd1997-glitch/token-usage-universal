from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path


_INSTANCE_CACHE: dict[str, "PricingDatabase"] = {}


class PricingDatabase:
    def __new__(cls, db_path: Path | None = None):
        resolved = (db_path or (Path(__file__).resolve().parent / "pricing_db.json")).resolve()
        cache_key = str(resolved)
        instance = _INSTANCE_CACHE.get(cache_key)
        if instance is not None:
            return instance
        instance = super().__new__(cls)
        _INSTANCE_CACHE[cache_key] = instance
        return instance

    def __init__(self, db_path: Path | None = None) -> None:
        resolved = (db_path or (Path(__file__).resolve().parent / "pricing_db.json")).resolve()
        if getattr(self, "_initialized", False) and getattr(self, "db_path", None) == resolved:
            return

        self.db_path = resolved
        self.models: dict[str, dict[str, float | str]] = {}
        self.aliases: dict[str, str] = {}
        self.verified_at: str | None = None
        self._cache: dict[str, dict[str, float | str] | None] = {}
        self._load()
        self._initialized = True

    def _load(self) -> None:
        if not self.db_path.exists():
            return
        payload = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.verified_at = str(payload.get("verified_at")).strip() or None if payload.get("verified_at") else None
        self.models = {str(key): value for key, value in payload.get("models", {}).items()}
        self.aliases = {
            self._normalize_alias_key(str(key)): str(value)
            for key, value in payload.get("aliases", {}).items()
        }

    @staticmethod
    def _coerce_reference_date(value: date | datetime | str | None) -> date:
        if value is None:
            return datetime.now().date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)).date()

    def verification_age_days(self, reference_date: date | datetime | str | None = None) -> int | None:
        if not self.verified_at:
            return None
        verified = datetime.fromisoformat(self.verified_at).date()
        return (self._coerce_reference_date(reference_date) - verified).days

    def verification_warning(
        self,
        *,
        reference_date: date | datetime | str | None = None,
        max_age_days: int = 90,
    ) -> str | None:
        age_days = self.verification_age_days(reference_date)
        if age_days is None:
            return "pricing_db.json 缺少 verified_at，请补充核验日期。"
        if age_days <= max_age_days:
            return None
        return (
            f"pricing_db.json 已有 {age_days} 天未核验；"
            f"当前 verified_at = {self.verified_at}，建议尽快复核价格表。"
        )

    @staticmethod
    def _normalize_alias_key(value: str) -> str:
        return re.sub(r"[\s_]+", "-", value.strip().lower()).strip("-")

    @classmethod
    def normalize_model_name(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = str(value).strip().lower().replace("\\", "/")
        normalized = re.sub(r"^(models?|model)[:/]", "", normalized)
        normalized = normalized.split("/")[-1]
        normalized = re.sub(r"[\s_]+", "-", normalized)
        normalized = re.sub(r"-+", "-", normalized).strip("-")
        return normalized or None

    @classmethod
    def _candidate_keys(cls, model: str, provider: str | None = None) -> list[str]:
        raw = (model or "").strip().lower()
        provider = (provider or "").strip().lower()
        base = raw.split("/")[-1]
        candidates = [raw, base]
        if provider:
            candidates.extend(
                [
                    f"{provider}/{raw}",
                    f"{provider}/{base}",
                ]
            )
        candidates.extend(
            [
                cls._normalize_alias_key(item)
                for item in (
                    raw,
                    base,
                    raw.replace(".", "-"),
                    base.replace(".", "-"),
                    raw.replace("-", "."),
                    base.replace("-", "."),
                )
                if item
            ]
        )
        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if item and item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped

    def resolve(self, model: str | None, provider: str | None = None) -> dict[str, float | str] | None:
        if not model:
            return None
        cache_key = f"{provider or ''}|{model}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        for candidate in self._candidate_keys(model, provider):
            resolved_key = self.aliases.get(candidate, candidate)
            pricing = self.models.get(resolved_key)
            if pricing:
                self._cache[cache_key] = pricing
                return pricing

        self._cache[cache_key] = None
        return None

    def canonical_model(self, model: str | None, provider: str | None = None) -> str | None:
        if not model:
            return None
        for candidate in self._candidate_keys(model, provider):
            resolved_key = self.aliases.get(candidate, candidate)
            if resolved_key in self.models:
                return resolved_key
        return self.normalize_model_name(model)

    @staticmethod
    def uncached_input_tokens(
        *,
        input_tokens: int | None,
        cached_input_tokens: int | None,
        output_tokens: int | None,
        reasoning_tokens: int | None,
        total_tokens: int | None,
    ) -> int:
        cached_value = int(cached_input_tokens or 0)
        output_value = int(output_tokens or 0)
        reasoning_value = int(reasoning_tokens or 0)
        if total_tokens is not None:
            return max(0, int(total_tokens) - cached_value - output_value - reasoning_value)

        input_value = int(input_tokens or 0)
        if cached_value:
            return max(0, input_value - cached_value)
        return input_value

    def estimate_cost(
        self,
        *,
        model: str | None,
        provider: str | None,
        input_tokens: int | None,
        cached_input_tokens: int | None,
        output_tokens: int | None,
        reasoning_tokens: int | None,
        total_tokens: int | None = None,
        count_cached_input: bool = False,
    ) -> float | None:
        pricing = self.resolve(model, provider)
        if not pricing:
            return None

        input_rate = float(pricing.get("input_per_million", 0.0) or 0.0)
        cached_rate = float(pricing.get("cached_input_per_million", input_rate * 0.1) or 0.0)
        output_rate = float(pricing.get("output_per_million", 0.0) or 0.0)
        reasoning_rate = float(pricing.get("reasoning_per_million", output_rate) or output_rate)
        uncached_input = self.uncached_input_tokens(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
        )

        total = (
            (uncached_input * input_rate)
            + ((int(cached_input_tokens or 0) * cached_rate) if count_cached_input else 0)
            + (int(output_tokens or 0) * output_rate)
            + (int(reasoning_tokens or 0) * reasoning_rate)
        ) / 1_000_000
        return round(total, 6)
