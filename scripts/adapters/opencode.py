from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_OPENCODE_BIN_ENV,
    TOKEN_USAGE_OPENCODE_ROOTS_ENV,
    default_opencode_roots,
    expand_path_text,
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


_SESSION_LIST_TIMEOUT_SECONDS = 10
_EXPORT_TIMEOUT_SECONDS = 12
_MAX_SESSION_EXPORTS = 80


def _flatten_roots(raw_value: str) -> list[Path]:
    if not raw_value.strip():
        return default_opencode_roots()
    return [Path(expand_path_text(item.strip())).expanduser() for item in raw_value.split(",") if item.strip()]


def _decode_json_output(raw_text: str):
    stripped = raw_text.lstrip()
    if not stripped:
        raise ValueError("empty output")
    if stripped[0] not in "[{":
        brace_positions = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
        if not brace_positions:
            raise ValueError("output did not contain JSON")
        stripped = stripped[min(brace_positions) :]
    payload, _ = json.JSONDecoder().raw_decode(stripped)
    return payload


def _iter_session_rows(node):
    if isinstance(node, list):
        for value in node:
            yield from _iter_session_rows(value)
        return
    if not isinstance(node, dict):
        return

    direct_session_id = node.get("id") or node.get("sessionID") or node.get("session_id")
    if direct_session_id not in (None, "") and any(
        key in node for key in ("title", "project", "cwd", "updated_at", "updatedAt", "created_at", "createdAt")
    ):
        yield node

    for key in ("sessions", "data", "items", "results"):
        value = node.get(key)
        if value is not None:
            yield from _iter_session_rows(value)


def _split_provider_model(provider: str, raw_model) -> tuple[str, str | None]:
    if raw_model in (None, ""):
        return provider, None
    raw_text = str(raw_model)
    if "/" not in raw_text:
        return provider, raw_text
    if provider and provider != "opencode":
        return provider, raw_text
    prefix, suffix = raw_text.split("/", 1)
    if prefix and suffix:
        return prefix, suffix
    return provider, raw_text


class OpenCodeAdapter(BaseAdapter):
    source_id = "opencode"
    display_name = "OpenCode"
    provider = "opencode"
    accuracy_level = "exact"
    parser_version = "opencode-cli-v1"

    def __init__(self) -> None:
        self.root_env = TOKEN_USAGE_OPENCODE_ROOTS_ENV
        self.bin_env = TOKEN_USAGE_OPENCODE_BIN_ENV
        self.roots = _flatten_roots(os.environ.get(self.root_env, ""))
        self._cli_inventory: dict[str, object] | None = None

    def _resolve_cli(self) -> str | None:
        configured = os.environ.get(self.bin_env, "").strip()
        if configured:
            return expand_path_text(configured)
        for candidate in ("opencode", "opencode.cmd", "opencode.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _existing_roots(self) -> list[Path]:
        return [path for path in self.roots if path.exists()]

    def _collect_local_markers(self) -> dict[str, object]:
        roots = self._existing_roots()
        log_files: list[Path] = []
        prompt_histories: list[Path] = []
        storage_markers: list[Path] = []

        for root in roots:
            log_files.extend(path for path in root.rglob("*.log") if path.is_file())
            prompt_histories.extend(path for path in root.rglob("prompt-history.jsonl") if path.is_file())
            storage_markers.extend(path for path in root.rglob("*.json") if path.is_file() and "storage" in path.parts)

        return {
            "roots": roots,
            "log_files": sorted({path for path in log_files}),
            "prompt_histories": sorted({path for path in prompt_histories}),
            "storage_markers": sorted({path for path in storage_markers}),
        }

    def _run_cli(self, *args: str, timeout: int):
        command = self._resolve_cli()
        if not command:
            raise FileNotFoundError("opencode executable not found")
        return subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )

    def _load_cli_inventory(self) -> dict[str, object]:
        if self._cli_inventory is not None:
            return self._cli_inventory

        inventory: dict[str, object] = {
            "available": False,
            "error": None,
            "sessions": [],
            "sample_events": [],
            "sample_session_id": None,
        }

        command = self._resolve_cli()
        if not command:
            self._cli_inventory = inventory
            return inventory

        try:
            listed = self._run_cli("session", "list", "--max-count", "8", "--format", "json", timeout=_SESSION_LIST_TIMEOUT_SECONDS)
            list_payload = _decode_json_output(listed.stdout)
            sessions = []
            seen_ids: set[str] = set()
            for row in _iter_session_rows(list_payload):
                session_id = row.get("id") or row.get("sessionID") or row.get("session_id")
                if session_id in (None, ""):
                    continue
                session_text = str(session_id)
                if session_text in seen_ids:
                    continue
                seen_ids.add(session_text)
                sessions.append(row)
            inventory["sessions"] = sessions
            if not sessions:
                inventory["available"] = True
                self._cli_inventory = inventory
                return inventory

            sample_session_id = str(sessions[0].get("id") or sessions[0].get("sessionID") or sessions[0].get("session_id"))
            inventory["sample_session_id"] = sample_session_id
            exported = self._run_cli("export", sample_session_id, timeout=_EXPORT_TIMEOUT_SECONDS)
            payload = _decode_json_output(exported.stdout)
            sample_events, _ = self._collect_export_payload(
                payload,
                exported_at=datetime.now().astimezone(),
                fallback_tz=datetime.now().astimezone().tzinfo,
                pricing=PricingDatabase(),
                session_id_hint=sample_session_id,
                source_path=f"opencode export {sample_session_id}",
            )
            inventory["sample_events"] = sample_events
            inventory["available"] = True
        except (FileNotFoundError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
            inventory["error"] = str(exc)

        self._cli_inventory = inventory
        return inventory

    def detect(self) -> SourceDetection:
        local = self._collect_local_markers()
        roots = list(local["roots"])
        log_files = list(local["log_files"])
        prompt_histories = list(local["prompt_histories"])
        storage_markers = list(local["storage_markers"])
        command = self._resolve_cli()
        cli_inventory = self._load_cli_inventory()
        sessions = list(cli_inventory["sessions"])
        sample_events = list(cli_inventory["sample_events"])
        details: list[str] = []

        if command:
            details.append(f"OpenCode CLI detected at {command}")
        if roots:
            details.append(
                f"detected {len(log_files)} log file(s), {len(prompt_histories)} prompt history file(s), and {len(storage_markers)} storage JSON file(s)"
            )

        if sample_events:
            details.append("OpenCode CLI export returned exact usage payloads from session JSON")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="OpenCode CLI export produced exact token usage records",
                candidate_paths=[str(roots[0])] if roots else [],
                details=details,
            )

        if command and cli_inventory["error"]:
            details.append(f"CLI probe failed: {cli_inventory['error']}")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "OpenCode CLI was found, but session export probing failed; check the CLI install and auth state"
                ),
                candidate_paths=[str(roots[0])] if roots else [],
                details=details,
            )

        if command and sessions:
            details.append("CLI session listing worked, but the sampled export did not expose exact usage fields")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="OpenCode sessions were listed, but the sampled export did not contain exact usage payloads",
                candidate_paths=[str(roots[0])] if roots else [],
                details=details,
            )

        if command:
            details.append("CLI is reachable, but no sessions were returned by `opencode session list --format json`")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="OpenCode CLI is installed, but no sessions were found yet",
                candidate_paths=[str(roots[0])] if roots else [],
                details=details,
            )

        if roots:
            details.append("local OpenCode files expose prompts, logs, and session metadata, but not exact token totals by themselves")
            details.append(f"set {TOKEN_USAGE_OPENCODE_BIN_ENV} if the CLI is installed outside PATH")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary=(
                    "OpenCode local data was detected, but exact token collection currently needs CLI export or token-bearing session JSON"
                ),
                candidate_paths=[str(roots[0]), *[str(path) for path in prompt_histories[:1]], *[str(path) for path in log_files[:1]]][:3],
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
                "OpenCode traces were not found; check local storage roots or set "
                f"{TOKEN_USAGE_OPENCODE_ROOTS_ENV} / {TOKEN_USAGE_OPENCODE_BIN_ENV}"
            ),
            candidate_paths=[str(path) for path in self.roots[:3]],
        )

    def _collect_export_payload(
        self,
        payload,
        *,
        exported_at: datetime,
        fallback_tz,
        pricing: PricingDatabase,
        session_id_hint: str,
        source_path: str,
    ) -> tuple[list[UsageEvent], list[str]]:
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        seen: set[tuple[str, str, str, int]] = set()
        used_exported_timestamp = False

        for carrier, usage in iter_usage_carriers(payload):
            usage_values = normalize_usage(usage)
            if usage_values["total_tokens"] <= 0:
                continue

            timestamp_value = find_first_value(carrier, TIMESTAMP_KEYS) or find_first_value(payload, TIMESTAMP_KEYS)
            if timestamp_value not in (None, ""):
                try:
                    timestamp = parse_timestamp(str(timestamp_value), fallback_tz)
                except (TypeError, ValueError) as exc:
                    verification_issues.append(f"invalid OpenCode export timestamp for {session_id_hint}: {exc}")
                    continue
            else:
                timestamp = exported_at
                used_exported_timestamp = True

            provider = str(find_first_value(carrier, PROVIDER_KEYS) or find_first_value(payload, PROVIDER_KEYS) or self.provider)
            raw_model = find_first_value(carrier, MODEL_KEYS) or find_first_value(payload, MODEL_KEYS)
            provider, raw_model = _split_provider_model(provider, raw_model)
            canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
            normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
            model_resolution = "unknown"
            if canonical_model:
                model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

            session_id = find_first_value(carrier, SESSION_KEYS) or find_first_value(payload, SESSION_KEYS) or session_id_hint
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
                    project_path=find_first_value(carrier, PROJECT_KEYS) or find_first_value(payload, PROJECT_KEYS),
                    model=canonical_model or raw_model,
                    input_tokens=usage_values["input_tokens"],
                    cached_input_tokens=usage_values["cached_input_tokens"],
                    output_tokens=usage_values["output_tokens"],
                    reasoning_tokens=usage_values["reasoning_tokens"],
                    total_tokens=usage_values["total_tokens"],
                    accuracy_level=self.accuracy_level,
                    raw_event_kind="opencode_export:session_json",
                    source_path=source_path,
                    raw_model=str(raw_model) if raw_model not in (None, "") else None,
                    model_resolution=model_resolution,
                    model_source="opencode_export" if raw_model not in (None, "") else None,
                )
            )

        if used_exported_timestamp:
            verification_issues.append(
                "some OpenCode export records lacked per-event timestamps, so export time was used as a fallback"
            )
        return events, verification_issues

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        cli_inventory = self._load_cli_inventory()
        sessions = list(cli_inventory["sessions"])
        if not cli_inventory["available"] or not sessions:
            return SourceCollectResult(
                detection=detection,
                scanned_files=len(sessions),
                verification_issues=[str(cli_inventory["error"])] if cli_inventory["error"] else [],
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
        exported_sessions = 0

        for row in sessions[:_MAX_SESSION_EXPORTS]:
            session_id = row.get("id") or row.get("sessionID") or row.get("session_id")
            if session_id in (None, ""):
                continue
            session_text = str(session_id)
            try:
                exported = self._run_cli("export", session_text, timeout=_EXPORT_TIMEOUT_SECONDS)
                payload = _decode_json_output(exported.stdout)
            except (FileNotFoundError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
                verification_issues.append(f"OpenCode export failed for {session_text}: {exc}")
                continue

            exported_sessions += 1
            payload_events, payload_issues = self._collect_export_payload(
                payload,
                exported_at=datetime.now().astimezone(),
                fallback_tz=fallback_tz,
                pricing=pricing,
                session_id_hint=session_text,
                source_path=f"opencode export {session_text}",
            )
            events.extend(event for event in payload_events if within_window(window, event.timestamp))
            verification_issues.extend(payload_issues)

        if not events and not verification_issues:
            verification_issues.append("no OpenCode exact usage records landed inside the selected time window")

        if events and not detection.available:
            detection = SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="OpenCode CLI export produced exact token usage records",
                candidate_paths=detection.candidate_paths,
                details=detection.details,
            )

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=exported_sessions,
            verification_issues=verification_issues[:10],
        )
