"""Anthropic Claude Code adapter.

Claude Code (the official Anthropic CLI / Claude Desktop "code mode") writes
per-session JSONL transcripts to::

    ~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl

The encoded directory name is the absolute cwd with ``/`` replaced by ``-``
(eg. ``/Users/me/AI/foo`` → ``-Users-me-AI-foo``). The real project path is
also embedded in every event under the ``cwd`` field, so we prefer that
over the mangled dirname.

Each line is a JSON event. Lines with ``type == "assistant"`` carry the
Anthropic usage payload at ``message.usage``:

    {
      "type": "assistant",
      "timestamp": "2026-05-09T06:28:09.369Z",
      "sessionId": "<uuid>",
      "cwd": "/Users/me/AI/foo",
      "message": {
        "model": "claude-opus-4-7",
        "usage": {
          "input_tokens": 6,
          "cache_creation_input_tokens": 47266,
          "cache_read_input_tokens": 15637,
          "output_tokens": 3381,
          ...
        }
      }
    }

Token semantics (Anthropic):
- ``input_tokens``                  — fresh prompt content (excludes cache)
- ``cache_creation_input_tokens``   — billable new cache writes
- ``cache_read_input_tokens``       — cheap cache hits
- ``output_tokens``                 — model output

For the universal model we fold cache_creation into "input" (it's billable),
and surface cache_read as ``cached_input_tokens`` so the "去缓存后" panel
correctly subtracts it.

Path override: export ``TOKEN_USAGE_CLAUDE_CODE_ROOT=/some/path`` to point at
a non-default location (eg. shared NFS, sandbox copy).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import (
    TOKEN_USAGE_CLAUDE_CODE_ROOT_ENV,
    default_claude_code_roots,
    expand_path_text,
)
from core.models import SourceCollectResult, SourceDetection, TimeWindow, UsageEvent
from core.time_window import parse_timestamp, within_window


def _resolve_roots(override: str | None = None) -> list[Path]:
    raw = override or os.environ.get(TOKEN_USAGE_CLAUDE_CODE_ROOT_ENV, "").strip()
    if raw:
        return [
            Path(expand_path_text(item.strip())).expanduser()
            for item in raw.split(",")
            if item.strip()
        ]
    return default_claude_code_roots()


def _decode_project_dirname(name: str) -> str:
    """Best-effort recovery of the cwd from the encoded dirname.

    Encoding is ``/`` → ``-``; the reverse is ambiguous when the original
    path itself contained ``-``. We only use this when an event lacks a
    ``cwd`` field. Real ``cwd`` from the event always wins.
    """
    if not name:
        return ""
    # Strip leading ``-`` then prepend ``/``
    if name.startswith("-"):
        return "/" + name[1:].replace("-", "/")
    return name.replace("-", "/")


def _extract_usage(event: dict) -> dict | None:
    msg = event.get("message")
    if not isinstance(msg, dict):
        return None
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None
    # Must look like Anthropic usage
    if "input_tokens" not in usage and "output_tokens" not in usage:
        return None
    return usage


def _int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


class ClaudeCodeAdapter(BaseAdapter):
    source_id = "claude-code"
    display_name = "Anthropic Claude Code"
    provider = "anthropic"
    accuracy_level = "exact"
    default_selected = True

    def _find_roots(self) -> list[Path]:
        return [root for root in _resolve_roots() if root.exists()]

    def _iter_jsonl_files(self, roots: list[Path]):
        for root in roots:
            try:
                for project_dir in root.iterdir():
                    if not project_dir.is_dir():
                        continue
                    try:
                        for child in project_dir.iterdir():
                            if child.is_file() and child.suffix == ".jsonl":
                                yield project_dir, child
                    except OSError:
                        continue
            except OSError:
                continue

    def detect(self) -> SourceDetection:
        candidate_paths = [str(p) for p in _resolve_roots()]
        roots = self._find_roots()

        if not roots:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="Claude Code project log directory not found",
                candidate_paths=candidate_paths,
                details=[
                    "No ~/.claude/projects directory detected on this machine.",
                    f"Override search path: export {TOKEN_USAGE_CLAUDE_CODE_ROOT_ENV}=<path>",
                ],
            )

        project_count = 0
        jsonl_count = 0
        latest_mtime: float | None = None
        sample_path = None
        for project_dir, jsonl_path in self._iter_jsonl_files(roots):
            if jsonl_count == 0:
                project_count = 1
                sample_path = jsonl_path
            jsonl_count += 1
            try:
                mtime = jsonl_path.stat().st_mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime
            except OSError:
                pass
        # second pass to count distinct projects (cheap: already iterated, but reset)
        seen_projects = set()
        for project_dir, _ in self._iter_jsonl_files(roots):
            seen_projects.add(project_dir)
        project_count = len(seen_projects)

        latest_str = (
            datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M")
            if latest_mtime
            else "unknown"
        )

        details = [
            f"Claude Code data root(s): {', '.join(str(r) for r in roots)}",
            f"Detected projects: {project_count}",
            f"Detected JSONL session files: {jsonl_count}",
            f"Most recent activity: {latest_str}",
        ]
        if sample_path is not None:
            details.append(f"Sample file: {sample_path}")

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=jsonl_count > 0,
            summary=(
                f"Claude Code detected — {project_count} project(s), "
                f"{jsonl_count} session file(s)"
            ),
            candidate_paths=candidate_paths,
            details=details,
        )

    def collect(self, window: TimeWindow) -> SourceCollectResult:
        detection = self.detect()
        if not detection.available:
            return SourceCollectResult(
                detection=detection,
                events=[],
                scanned_files=0,
                skipped_reasons=[detection.summary],
            )

        roots = self._find_roots()
        events: list[UsageEvent] = []
        scanned = 0

        # Determine tz for naive timestamps: prefer window.start, then window.end,
        # else UTC. Claude Code timestamps are ISO-8601 with explicit "Z", so
        # this only matters as a defensive fallback.
        from datetime import timezone as _tz
        tzinfo = (
            (window.start.tzinfo if window.start else None)
            or (window.end.tzinfo if window.end else None)
            or _tz.utc
        )
        verification_issues: list[str] = []
        bad_lines = 0
        no_usage_files = 0
        skipped_old = 0

        for project_dir, jsonl_path in self._iter_jsonl_files(roots):
            scanned += 1
            had_usage = False
            # Cheap mtime filter: if file's mtime is well before window.start, skip.
            if window.start is not None:
                try:
                    mtime = datetime.fromtimestamp(
                        jsonl_path.stat().st_mtime, tz=window.start.tzinfo
                    )
                    if mtime < window.start:
                        skipped_old += 1
                        continue
                except OSError:
                    pass

            try:
                f = jsonl_path.open("r", encoding="utf-8", errors="replace")
            except OSError as exc:
                verification_issues.append(f"{jsonl_path.name}: open failed ({exc})")
                continue

            with f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        bad_lines += 1
                        continue
                    if not isinstance(event, dict):
                        continue

                    usage = _extract_usage(event)
                    if usage is None:
                        continue

                    ts_raw = event.get("timestamp") or event.get("created_at")
                    try:
                        timestamp = parse_timestamp(str(ts_raw), tzinfo) if ts_raw else None
                    except (ValueError, TypeError):
                        timestamp = None
                    if timestamp is None:
                        continue
                    if not within_window(window, timestamp):
                        continue

                    msg = event.get("message") or {}
                    raw_model = msg.get("model") or event.get("model")
                    model_text = str(raw_model) if raw_model else None

                    session_id = (
                        event.get("sessionId")
                        or event.get("session_id")
                        or jsonl_path.stem
                    )

                    cwd = event.get("cwd") or _decode_project_dirname(project_dir.name)

                    input_tokens = _int(usage.get("input_tokens"))
                    cache_creation = _int(usage.get("cache_creation_input_tokens"))
                    cache_read = _int(usage.get("cache_read_input_tokens"))
                    output_tokens = _int(usage.get("output_tokens"))

                    # Billable fresh input = small input_tokens + cache writes.
                    # Cache reads are surfaced separately as cached_input_tokens
                    # so the "去缓存后" view can subtract them.
                    fresh_input = input_tokens + cache_creation
                    cached_input = cache_read
                    total = fresh_input + cached_input + output_tokens

                    events.append(
                        UsageEvent(
                            source=self.source_id,
                            provider=self.provider,
                            timestamp=timestamp,
                            session_id=str(session_id),
                            project_path=str(cwd) if cwd else None,
                            model=model_text,
                            input_tokens=fresh_input,
                            cached_input_tokens=cached_input,
                            output_tokens=output_tokens,
                            reasoning_tokens=None,
                            total_tokens=total,
                            accuracy_level=self.accuracy_level,
                            raw_event_kind="claude_code.assistant_usage",
                            source_path=str(jsonl_path),
                            raw_model=model_text,
                            model_resolution="exact" if model_text else "unknown",
                            model_source="message.model",
                        )
                    )
                    had_usage = True

            if not had_usage:
                no_usage_files += 1

        skipped_reasons: list[str] = []
        if bad_lines:
            verification_issues.append(f"{bad_lines} unparseable JSONL line(s) skipped")
        if no_usage_files and not events:
            skipped_reasons.append(
                f"{no_usage_files} JSONL file(s) had no assistant usage events"
            )
        if skipped_old:
            skipped_reasons.append(
                f"{skipped_old} file(s) skipped via mtime (older than window start)"
            )

        return SourceCollectResult(
            detection=detection,
            events=events,
            scanned_files=scanned,
            verification_issues=verification_issues,
            skipped_reasons=skipped_reasons,
        )
