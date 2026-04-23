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
from core.robust_read import read_json_robust
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


def _read_json_file(path: Path):
    payload, _encoding = read_json_robust(path)
    return payload


def _extract_sessions_from_global_dat(payload) -> list[dict]:
    """opencode.global.dat is JSON on some builds. Schema varies by version;
    accept any of:
      - top-level list of session dicts
      - {"sessions": [...]}
      - {"storage": {"session": {...}}} — nested storage shape
      - dict-of-sessions: {session_id: {...}, ...}
    Returns a (possibly empty) list of session dicts, each normalized to
    contain at least `id` and, when available, `directory` / `projectID`.
    """
    if payload is None:
        return []
    candidates: list = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("sessions"), list):
            candidates = payload["sessions"]
        elif isinstance(payload.get("storage"), dict):
            session_block = payload["storage"].get("session")
            if isinstance(session_block, dict):
                candidates = list(session_block.values())
            elif isinstance(session_block, list):
                candidates = session_block
        else:
            # dict-of-sessions heuristic: all values look like session dicts
            values = [v for v in payload.values() if isinstance(v, dict)]
            if values and any(("id" in v or "sessionID" in v) for v in values):
                candidates = values

    sessions: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        sid = item.get("id") or item.get("sessionID") or item.get("session_id")
        if not sid:
            continue
        normalized = dict(item)
        normalized.setdefault("id", sid)
        sessions.append(normalized)
    return sessions


def _looks_like_opencode_export_shape(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return False
    for item in messages:
        if not isinstance(item, dict):
            continue
        info = item.get("info")
        parts = item.get("parts")
        if isinstance(info, dict) and isinstance(parts, list):
            return True
    return False


def _read_json_file_with_encoding(path: Path):
    """Return (payload, encoding_used). encoding_used is None on failure,
    a codec name on success, or 'utf-8:replace' when lossy fallback was needed.
    Adapters call this on hot paths (message JSON) to surface GBK / corruption
    issues via verification_issues instead of silently skipping files.
    """
    return read_json_robust(path)


def _parse_epoch_millis(value, fallback_tz):
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=fallback_tz)
    except (TypeError, ValueError, OSError):
        return None


class OpenCodeAdapter(BaseAdapter):
    source_id = "opencode"
    display_name = "OpenCode"
    provider = "opencode"
    accuracy_level = "exact"
    parser_version = "opencode-v2"

    def __init__(self) -> None:
        self.root_env = TOKEN_USAGE_OPENCODE_ROOTS_ENV
        self.bin_env = TOKEN_USAGE_OPENCODE_BIN_ENV
        self.roots = _flatten_roots(os.environ.get(self.root_env, ""))
        self._cli_inventory: dict[str, object] | None = None
        self._local_inventory: dict[str, object] | None = None

    def _resolve_cli(self) -> str | None:
        configured = os.environ.get(self.bin_env, "").strip()
        if configured:
            return expand_path_text(configured)
        # On Windows, `opencode.exe` (GUI) and `opencode-cli.exe` (CLI) may
        # both exist in PATH; prefer the CLI one — the GUI binary either
        # doesn't support `session list` / `export` or launches a window.
        # Fall back to the plain name for macOS/Linux and older installs.
        for candidate in (
            "opencode-cli",
            "opencode-cli.cmd",
            "opencode-cli.exe",
            "opencode",
            "opencode.cmd",
            "opencode.exe",
        ):
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
        session_files: list[Path] = []
        message_files: list[Path] = []
        # Newer OpenCode builds (notably the Windows desktop) don't write
        # the per-session / per-message JSON trees — everything lives in a
        # monolithic .dat file (despite the extension, it's JSON on builds
        # observed in the wild; LevelDB on others). Collect both patterns
        # so downstream code can fall back when storage/*.json is empty.
        global_dat_files: list[Path] = []

        for root in roots:
            log_files.extend(path for path in root.rglob("*.log") if path.is_file())
            prompt_histories.extend(path for path in root.rglob("prompt-history.jsonl") if path.is_file())
            storage_markers.extend(path for path in root.rglob("*.json") if path.is_file() and "storage" in path.parts)
            session_files.extend(path for path in root.rglob("storage/session/**/*.json") if path.is_file())
            message_files.extend(path for path in root.rglob("storage/message/**/*.json") if path.is_file())
            global_dat_files.extend(path for path in root.rglob("*.global.dat") if path.is_file())
            global_dat_files.extend(path for path in root.rglob("opencode.global.dat") if path.is_file())

        return {
            "roots": roots,
            "log_files": sorted({path for path in log_files}),
            "prompt_histories": sorted({path for path in prompt_histories}),
            "global_dat_files": sorted({path for path in global_dat_files}),
            "storage_markers": sorted({path for path in storage_markers}),
            "session_files": sorted({path for path in session_files}),
            "message_files": sorted({path for path in message_files}),
        }

    def _run_cli(self, *args: str, timeout: int, cwd: str | None = None):
        command = self._resolve_cli()
        if not command:
            raise FileNotFoundError("opencode executable not found")
        # Windows subprocess with text=True decodes stdout using the system
        # codepage (GBK/cp936 on Chinese Windows). OpenCode CLI writes UTF-8,
        # so GBK decode blows up on Chinese filenames. Read raw bytes and
        # decode UTF-8 explicitly with errors="replace" so we never crash
        # the adapter even if a stray non-UTF-8 byte slips in.
        raw = subprocess.run(
            [command, *args],
            capture_output=True,
            check=True,
            timeout=timeout,
            cwd=cwd,
        )
        return subprocess.CompletedProcess(
            args=raw.args,
            returncode=raw.returncode,
            stdout=raw.stdout.decode("utf-8", errors="replace"),
            stderr=raw.stderr.decode("utf-8", errors="replace"),
        )

    def _load_local_inventory(self) -> dict[str, object]:
        if self._local_inventory is not None:
            return self._local_inventory

        local = self._collect_local_markers()
        session_files = list(local["session_files"])
        message_files = list(local["message_files"])
        session_index: dict[str, dict[str, object]] = {}
        project_roots: dict[str, str] = {}
        verification_issues: list[str] = []
        events: list[UsageEvent] = []
        pricing = PricingDatabase()
        fallback_tz = datetime.now().astimezone().tzinfo

        for path in session_files:
            payload = _read_json_file(path)
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("id") or payload.get("sessionID") or payload.get("session_id")
            if session_id not in (None, ""):
                session_index[str(session_id)] = payload

        for path in local["storage_markers"]:
            if not isinstance(path, Path) or "project" not in path.parts:
                continue
            payload = _read_json_file(path)
            if not isinstance(payload, dict):
                continue
            project_id = payload.get("id")
            worktree = payload.get("worktree")
            if project_id not in (None, "") and worktree not in (None, ""):
                project_roots[str(project_id)] = str(worktree)

        seen: set[tuple[str, str]] = set()
        legacy_codec_hits = 0
        lossy_decode_hits = 0
        unreadable_files = 0
        for path in message_files:
            payload, encoding_used = _read_json_file_with_encoding(path)
            if encoding_used is None:
                unreadable_files += 1
                continue
            if encoding_used not in ("utf-8", "utf-8-sig") and encoding_used != "utf-8:replace":
                legacy_codec_hits += 1
            elif encoding_used == "utf-8:replace":
                lossy_decode_hits += 1
            if not isinstance(payload, dict) or payload.get("role") != "assistant":
                continue

            tokens = payload.get("tokens")
            if not isinstance(tokens, dict):
                continue
            cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
            uncached_input_tokens = int(tokens.get("input", 0) or 0)
            cache_read_tokens = int(cache.get("read", 0) or 0)
            cache_write_tokens = int(cache.get("write", 0) or 0)
            output_tokens = int(tokens.get("output", 0) or 0)
            reasoning_tokens = int(tokens.get("reasoning", 0) or 0)

            input_tokens = uncached_input_tokens + cache_write_tokens
            total_tokens = input_tokens + cache_read_tokens + output_tokens + reasoning_tokens
            if total_tokens <= 0:
                continue

            session_id = str(payload.get("sessionID") or payload.get("session_id") or "")
            if not session_id:
                verification_issues.append(f"missing session id in local OpenCode message {path}")
                continue

            message_id = str(payload.get("id") or path.stem)
            dedupe_key = (session_id, message_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            session_payload = session_index.get(session_id, {})
            session_time = session_payload.get("time") if isinstance(session_payload.get("time"), dict) else {}
            time_payload = payload.get("time") if isinstance(payload.get("time"), dict) else {}
            timestamp = (
                _parse_epoch_millis(time_payload.get("completed"), fallback_tz)
                or _parse_epoch_millis(time_payload.get("created"), fallback_tz)
                or _parse_epoch_millis(session_time.get("updated"), fallback_tz)
                or _parse_epoch_millis(session_time.get("created"), fallback_tz)
            )
            if timestamp is None:
                verification_issues.append(f"missing timestamp in local OpenCode message {path}")
                continue

            provider = str(payload.get("providerID") or self.provider)
            raw_model = payload.get("modelID")
            provider, raw_model = _split_provider_model(provider, raw_model)
            canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
            normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
            model_resolution = "unknown"
            if canonical_model:
                model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

            path_payload = payload.get("path") if isinstance(payload.get("path"), dict) else {}
            project_path = (
                path_payload.get("root")
                or path_payload.get("cwd")
                or session_payload.get("directory")
                or project_roots.get(str(session_payload.get("projectID") or ""))
            )

            events.append(
                UsageEvent(
                    source=self.source_id,
                    provider=provider,
                    timestamp=timestamp,
                    session_id=session_id,
                    project_path=str(project_path) if project_path not in (None, "") else None,
                    model=canonical_model or raw_model,
                    input_tokens=input_tokens,
                    cached_input_tokens=cache_read_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens,
                    total_tokens=total_tokens,
                    accuracy_level=self.accuracy_level,
                    raw_event_kind="opencode_local:message_json",
                    source_path=str(path),
                    raw_model=str(raw_model) if raw_model not in (None, "") else None,
                    model_resolution=model_resolution,
                    model_source="opencode_local" if raw_model not in (None, "") else None,
                )
            )

        if unreadable_files > 0:
            verification_issues.append(
                f"{unreadable_files} OpenCode message file(s) could not be decoded as "
                "UTF-8 / GBK / GB18030 — they may be corrupted or in an unsupported encoding"
            )
        if legacy_codec_hits > 0:
            verification_issues.append(
                f"{legacy_codec_hits} OpenCode message file(s) were decoded using a legacy "
                "codec (GBK/GB18030) — OpenCode likely wrote under a non-UTF-8 system codepage; "
                "set PYTHONIOENCODING=gbk or switch the host locale to UTF-8 to make this stable"
            )
        if lossy_decode_hits > 0:
            verification_issues.append(
                f"{lossy_decode_hits} OpenCode message file(s) required lossy fallback decoding; "
                "some text fields may be corrupted but token counts are preserved"
            )

        self._local_inventory = {
            "events": events,
            "verification_issues": verification_issues,
            "session_files": session_files,
            "message_files": message_files,
        }
        return self._local_inventory

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
            # --max-count is not in every opencode build; slice the result
            # in Python instead so older/variant CLIs (which silently fail
            # on unknown args) still return a valid list here.
            listed = self._run_cli("session", "list", "--format", "json", timeout=_SESSION_LIST_TIMEOUT_SECONDS)
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

            # Fallback: `opencode session list` is project-scoped — when
            # invoked from a dir that isn't any session's project root, it
            # returns [] even though sessions exist. Desktop builds in
            # particular only expose the global session registry via
            # opencode.global.dat. Merge those in so we can still call
            # `export <id>` with the right cwd per session.
            dat_sessions = self._sessions_from_global_dat()
            for row in dat_sessions:
                sid = str(row.get("id") or "")
                if not sid or sid in seen_ids:
                    continue
                seen_ids.add(sid)
                sessions.append(row)

            inventory["sessions"] = sessions
            if not sessions:
                inventory["available"] = True
                self._cli_inventory = inventory
                return inventory

            sample_session_id = str(sessions[0].get("id") or sessions[0].get("sessionID") or sessions[0].get("session_id"))
            inventory["sample_session_id"] = sample_session_id

            # Apply the same "prefer local-sourced cwd, skip mojibake" logic
            # as the main collect() path so detect-phase sample export also
            # survives Windows cp936 session-list output.
            sample_cwd: str | None = None
            local_cwd_map = self._build_session_cwd_map_from_local()
            candidate = local_cwd_map.get(sample_session_id) or sessions[0].get("directory")
            if isinstance(candidate, str) and candidate:
                try:
                    if Path(candidate).is_dir():
                        sample_cwd = candidate
                except (OSError, ValueError):
                    sample_cwd = None

            exported = self._run_cli("export", sample_session_id, timeout=_EXPORT_TIMEOUT_SECONDS, cwd=sample_cwd)
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
        session_files = list(local["session_files"])
        message_files = list(local["message_files"])
        local_inventory = self._load_local_inventory()
        local_events = list(local_inventory["events"])
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
        if session_files or message_files:
            details.append(
                f"found {len(session_files)} local session JSON file(s) and {len(message_files)} local message JSON file(s)"
            )

        if local_events:
            details.append("OpenCode local storage yielded exact token usage records from assistant message JSON")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=True,
                summary="OpenCode local storage produced exact token usage records",
                candidate_paths=[str(local_events[0].source_path)] if local_events[0].source_path else ([str(roots[0])] if roots else []),
                details=details,
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
                summary="OpenCode CLI was found, but session export probing failed; check the CLI install and auth state",
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
            details.append("local OpenCode files expose prompts, logs, and session metadata, but no assistant token JSON was usable yet")
            details.append(f"set {TOKEN_USAGE_OPENCODE_BIN_ENV} if the CLI is installed outside PATH")
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="OpenCode local data was detected, but no exact token-bearing assistant message JSON or CLI export was available",
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
        # OpenCode v1.1.13+ export layout puts metadata and token numbers
        # in sibling nodes: {"messages": [{"info": {...}, "parts": [{"tokens": ...}]}]}
        # iter_usage_carriers can't see across siblings, so route this
        # specific shape through a dedicated parser first. Any other layout
        # (older OpenCode, or generic payloads) falls back to the generic walker.
        if _looks_like_opencode_export_shape(payload):
            return self._collect_opencode_export_messages(
                payload,
                exported_at=exported_at,
                fallback_tz=fallback_tz,
                pricing=pricing,
                session_id_hint=session_id_hint,
                source_path=source_path,
            )

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

    def _collect_opencode_export_messages(
        self,
        payload: dict,
        *,
        exported_at: datetime,
        fallback_tz,
        pricing: PricingDatabase,
        session_id_hint: str,
        source_path: str,
    ) -> tuple[list[UsageEvent], list[str]]:
        """Parse OpenCode v1.1.13+ export layout.

        Token numbers live in `messages[i].parts[j].tokens` but the per-message
        metadata (role / modelID / providerID / time / path) lives in
        `messages[i].info`. iter_usage_carriers can't associate siblings, so
        we walk the structure explicitly and emit one event per assistant
        message (not per part — parts usually share identical token counts
        because OpenCode reports cumulative tokens on each reasoning chunk).
        """
        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        seen: set[tuple[str, str, int]] = set()

        for message in payload.get("messages", []):
            if not isinstance(message, dict):
                continue
            info = message.get("info") if isinstance(message.get("info"), dict) else {}
            parts = message.get("parts") if isinstance(message.get("parts"), list) else []
            if info.get("role") != "assistant":
                continue

            # Pick the part with the largest total tokens — OpenCode writes
            # cumulative counts on every part, so the last / max one is the
            # real message total. Using max() is order-independent.
            best_usage = None
            for part in parts:
                if not isinstance(part, dict):
                    continue
                token_block = part.get("tokens")
                if not isinstance(token_block, dict):
                    continue
                usage_values = normalize_usage(token_block)
                if usage_values["total_tokens"] <= 0:
                    continue
                if best_usage is None or usage_values["total_tokens"] > best_usage["total_tokens"]:
                    best_usage = usage_values
            if best_usage is None:
                continue

            time_block = info.get("time") if isinstance(info.get("time"), dict) else {}
            epoch_ms = time_block.get("completed") or time_block.get("created")
            if isinstance(epoch_ms, (int, float)):
                try:
                    timestamp = datetime.fromtimestamp(int(epoch_ms) / 1000, tz=fallback_tz)
                except (TypeError, ValueError, OSError) as exc:
                    verification_issues.append(
                        f"invalid OpenCode export timestamp for {session_id_hint}: {exc}"
                    )
                    timestamp = exported_at
            else:
                timestamp = exported_at
                verification_issues.append(
                    f"OpenCode export message lacked time.completed/created for {session_id_hint}"
                )

            provider_raw = str(info.get("providerID") or self.provider)
            raw_model = info.get("modelID")
            provider, raw_model = _split_provider_model(provider_raw, raw_model)
            canonical_model = pricing.canonical_model(raw_model, provider) if raw_model else None
            normalized_raw_model = pricing.normalize_model_name(raw_model) if raw_model else None
            model_resolution = "unknown"
            if canonical_model:
                model_resolution = "exact" if canonical_model == normalized_raw_model else "alias"

            path_block = info.get("path") if isinstance(info.get("path"), dict) else {}
            project_path = path_block.get("root") or path_block.get("cwd")

            session_id = str(info.get("sessionID") or session_id_hint)
            message_id = str(info.get("id") or info.get("messageID") or "")
            dedupe_key = (session_id, message_id, best_usage["total_tokens"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            events.append(
                UsageEvent(
                    source=self.source_id,
                    provider=provider,
                    timestamp=timestamp,
                    session_id=session_id,
                    project_path=str(project_path) if project_path not in (None, "") else None,
                    model=canonical_model or raw_model,
                    input_tokens=best_usage["input_tokens"],
                    cached_input_tokens=best_usage["cached_input_tokens"],
                    output_tokens=best_usage["output_tokens"],
                    reasoning_tokens=best_usage["reasoning_tokens"],
                    total_tokens=best_usage["total_tokens"],
                    accuracy_level=self.accuracy_level,
                    raw_event_kind="opencode_export:v1_1_13_messages",
                    source_path=source_path,
                    raw_model=str(raw_model) if raw_model not in (None, "") else None,
                    model_resolution=model_resolution,
                    model_source="opencode_export_messages" if raw_model not in (None, "") else None,
                )
            )

        return events, verification_issues

    def _sessions_from_global_dat(self) -> list[dict]:
        """Read all opencode.global.dat files discovered on this host and
        return the merged, de-duplicated list of session metadata dicts.
        Empty list if no .dat files exist or none are JSON-parseable.
        """
        local = self._collect_local_markers()
        seen: set[str] = set()
        out: list[dict] = []
        for path in local.get("global_dat_files", []):
            payload = _read_json_file(path)
            for session in _extract_sessions_from_global_dat(payload):
                sid = str(session.get("id") or "")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                out.append(session)
        return out

    def _build_session_cwd_map_from_local(self) -> dict[str, str]:
        """Derive session-id -> project cwd from local message / session
        JSON and, as a fallback, from opencode.global.dat.

        Trusted because OpenCode writes these files as UTF-8 JSON, so
        Chinese / non-ASCII paths survive intact. `session list --format json`
        output via subprocess.run can get mojibake'd on Windows GBK hosts.
        """
        mapping: dict[str, str] = {}
        local = self._collect_local_markers()

        # First pass: message JSON carries both sessionID and path.root per event.
        for path in local.get("message_files", []):
            payload = _read_json_file(path)
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("sessionID") or payload.get("session_id")
            path_block = payload.get("path") if isinstance(payload.get("path"), dict) else {}
            root = path_block.get("root") or path_block.get("cwd")
            if session_id and isinstance(root, str) and root and session_id not in mapping:
                mapping[str(session_id)] = root

        # Second pass: session JSON often stores a `directory` for sessions
        # whose first message file hasn't been visited yet.
        for path in local.get("session_files", []):
            payload = _read_json_file(path)
            if not isinstance(payload, dict):
                continue
            session_id = payload.get("id") or payload.get("sessionID")
            directory = payload.get("directory")
            if session_id and isinstance(directory, str) and directory and session_id not in mapping:
                mapping[str(session_id)] = directory

        # Third pass: opencode.global.dat (desktop builds that skip the
        # storage/session JSON trees). Each session dict may carry
        # `directory` / `projectID.worktree` / `path.root` — pick the first
        # existing.
        for session in self._sessions_from_global_dat():
            sid = str(session.get("id") or "")
            if not sid or sid in mapping:
                continue
            cwd = session.get("directory") or session.get("cwd")
            if not cwd:
                path_block = session.get("path") if isinstance(session.get("path"), dict) else {}
                cwd = path_block.get("root") or path_block.get("cwd")
            if not cwd:
                project = session.get("projectID") if isinstance(session.get("projectID"), dict) else {}
                cwd = project.get("worktree") if isinstance(project, dict) else None
            if isinstance(cwd, str) and cwd:
                mapping[sid] = cwd

        return mapping

    def collect(self, window) -> SourceCollectResult:
        detection = self.detect()
        local_inventory = self._load_local_inventory()
        local_events = [event for event in local_inventory["events"] if within_window(window, event.timestamp)]
        if local_inventory["events"]:
            return SourceCollectResult(
                detection=detection,
                events=local_events,
                scanned_files=len(local_inventory["message_files"]),
                verification_issues=list(local_inventory["verification_issues"])[:10],
            )

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
        fallback_tz = window.start.tzinfo if window.start else datetime.now().astimezone().tzinfo

        # OpenCode CLI `export` only finds a session when invoked from the
        # session's own project directory. Build session-id -> cwd from
        # LOCAL message JSON files (which OpenCode writes as UTF-8 JSON,
        # reliable) instead of from CLI `session list` output (which gets
        # mangled into mojibake when subprocess reads via cp936 on Windows
        # GBK hosts). Skip any path that doesn't exist on this machine
        # rather than letting subprocess crash with NotADirectoryError.
        session_cwd_map = self._build_session_cwd_map_from_local()

        events: list[UsageEvent] = []
        verification_issues: list[str] = []
        exported_sessions = 0
        skipped_for_missing_cwd = 0

        for row in sessions[:_MAX_SESSION_EXPORTS]:
            session_id = row.get("id") or row.get("sessionID") or row.get("session_id")
            if session_id in (None, ""):
                continue
            session_text = str(session_id)

            # Prefer a locally-sourced cwd. Fall back to whatever session
            # list reported (usually correct on UTF-8 hosts). If neither
            # yields an existing path, still try export without cwd — it
            # works on many setups and failing cleanly is fine either way.
            cwd_candidate = session_cwd_map.get(session_text)
            if cwd_candidate is None:
                raw_dir = row.get("directory") or row.get("cwd") or row.get("projectPath")
                if isinstance(raw_dir, str) and raw_dir:
                    cwd_candidate = raw_dir
            export_cwd: str | None = None
            if cwd_candidate:
                try:
                    if Path(cwd_candidate).is_dir():
                        export_cwd = cwd_candidate
                    else:
                        skipped_for_missing_cwd += 1
                except (OSError, ValueError):
                    # Mojibake unicode codepoints can raise OSError on Windows
                    # when stat'd; treat as "no valid cwd" and carry on.
                    skipped_for_missing_cwd += 1

            try:
                exported = self._run_cli(
                    "export", session_text, timeout=_EXPORT_TIMEOUT_SECONDS, cwd=export_cwd,
                )
                payload = _decode_json_output(exported.stdout)
            except (FileNotFoundError, subprocess.SubprocessError, ValueError, json.JSONDecodeError, OSError) as exc:
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

        if skipped_for_missing_cwd > 0:
            verification_issues.append(
                f"{skipped_for_missing_cwd} OpenCode session(s) had a project path that "
                "didn't exist on this machine (likely mojibake from a Windows cp936 host); "
                "CLI export was attempted without cwd"
            )

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
