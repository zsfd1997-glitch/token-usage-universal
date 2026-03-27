from __future__ import annotations

import json
import os
import re
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import TOKEN_USAGE_CODEX_ROOT_ENV, resolve_path_override
from core.models import SourceCollectResult, SourceDetection, UsageEvent
from core.time_window import parse_timestamp, within_window


_MODEL_TEXT_RE = re.compile(r"\b(GPT-\d+(?:\.\d+)?(?:-Codex)?)\b", re.IGNORECASE)


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

    return None


class CodexAdapter(BaseAdapter):
    source_id = "codex"
    display_name = "Codex"
    provider = "openai"
    accuracy_level = "exact"

    def __init__(self) -> None:
        self.root = resolve_path_override(
            TOKEN_USAGE_CODEX_ROOT_ENV,
            Path.home() / ".codex" / "sessions",
        )

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

    def _scan_files(self, start_ts: float | None) -> list[Path]:
        files = list(self.root.rglob("*.jsonl"))
        if start_ts is None:
            return sorted(files)
        cutoff = start_ts - 86400
        candidates: list[Path] = []
        for path in files:
            try:
                if path.stat().st_mtime >= cutoff:
                    candidates.append(path)
            except FileNotFoundError:
                continue
        return sorted(candidates)

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(detection=detection, skipped_reasons=[detection.summary])

        files = self._scan_files(window.start.timestamp() if window.start else None)
        events: list[UsageEvent] = []
        verification_issues: list[str] = []

        for path in files:
            session_id = path.stem
            project_path = None
            provider = self.provider
            model = None
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
                        if record_type == "session_meta":
                            session_id = payload.get("id") or session_id
                            project_path = payload.get("cwd") or project_path
                            provider = payload.get("model_provider") or provider
                            model = _infer_model_name(payload) or model
                            continue

                        if record_type != "event_msg" or payload.get("type") != "token_count":
                            continue

                        info = payload.get("info")
                        if not isinstance(info, dict):
                            continue

                        total_usage = info.get("total_token_usage")
                        if not isinstance(total_usage, dict):
                            continue

                        model = (
                            payload.get("model")
                            or payload.get("model_name")
                            or model
                        )

                        current_total = _normalize_usage(total_usage)
                        if previous_total is None:
                            delta_usage = current_total
                        else:
                            if current_total == previous_total:
                                continue
                            delta_usage = _subtract_usage(current_total, previous_total)
                            if min(delta_usage.values()) < 0:
                                last_usage = info.get("last_token_usage")
                                if isinstance(last_usage, dict):
                                    delta_usage = _normalize_usage(last_usage)
                                    verification_issues.append(
                                        f"negative total delta fallback to last_token_usage in {path}"
                                    )
                                else:
                                    verification_issues.append(
                                        f"negative total delta skipped in {path}"
                                    )
                                    previous_total = current_total
                                    continue

                        previous_total = current_total
                        fallback_tz = (
                            window.start.tzinfo
                            if window.start
                            else __import__("datetime").datetime.now().astimezone().tzinfo
                        )
                        timestamp = parse_timestamp(record["timestamp"], fallback_tz)
                        if not within_window(window, timestamp):
                            continue

                        events.append(
                            UsageEvent(
                                source=self.source_id,
                                provider=provider,
                                timestamp=timestamp,
                                session_id=str(session_id),
                                project_path=project_path,
                                model=model,
                                input_tokens=delta_usage["input_tokens"],
                                cached_input_tokens=delta_usage["cached_input_tokens"],
                                output_tokens=delta_usage["output_tokens"],
                                reasoning_tokens=delta_usage["reasoning_tokens"],
                                total_tokens=delta_usage["total_tokens"],
                                accuracy_level=self.accuracy_level,
                                raw_event_kind="token_count:delta",
                                source_path=str(path),
                            )
                        )
            except OSError as exc:
                verification_issues.append(f"failed reading {path}: {exc}")

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=len(files),
            verification_issues=verification_issues[:10],
        )
