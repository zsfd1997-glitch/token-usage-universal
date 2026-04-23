"""One-time environment probe + disk cache for active source IDs.

Problem being solved: the repo ships 51 adapters (Codex / Claude variants /
OpenCode / Trae / plus ~40 provider-API + chromium-desktop-family members).
On every `report` / `health` call we used to detect() all 51, but on a
typical machine only 3-8 actually have data. 46 wasted detect()s per
invocation add up to seconds of overhead, most of it in the 3-4 adapters
that do deep Chromium-cache / JSONL-tree walks.

Strategy: on the first run, run the full detect() sweep ONCE and remember
which source IDs found any trace on this host. Subsequent runs skip the
dead adapters entirely until the cache expires (TTL) or the user forces a
re-probe (`probe` subcommand, `--refresh` flag, or `TOKEN_USAGE_SOURCES`
env override).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core.config import default_cache_root


_SCHEMA_VERSION = 1
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def environment_cache_path() -> Path:
    return default_cache_root() / "environment.json"


def load_active_source_ids(*, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> set[str] | None:
    """Return the cached set of active source IDs, or None if:
      - cache file missing
      - cache file unreadable / corrupted
      - cache expired (older than ttl_seconds)
      - schema mismatch
    """
    path = environment_cache_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != _SCHEMA_VERSION:
        return None
    probed_at_raw = data.get("probed_at")
    if not isinstance(probed_at_raw, str):
        return None
    try:
        probed_at = datetime.fromisoformat(probed_at_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    age = (datetime.now(timezone.utc) - probed_at.astimezone(timezone.utc)).total_seconds()
    if age > ttl_seconds:
        return None
    ids = data.get("active_source_ids")
    if not isinstance(ids, list):
        return None
    return {str(sid) for sid in ids if sid}


def save_active_source_ids(active_ids: Iterable[str]) -> Path:
    """Write the probe result to the cache file. Returns the written path."""
    path = environment_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "probed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": _DEFAULT_TTL_SECONDS,
        "active_source_ids": sorted({str(sid) for sid in active_ids if sid}),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def invalidate_cache() -> bool:
    """Delete the cache file. Returns True if a file was removed."""
    path = environment_cache_path()
    if path.is_file():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False


def parse_env_filter(value: str) -> set[str]:
    """Parse TOKEN_USAGE_SOURCES='opencode,claude-code,codex' env value."""
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def pick_active_from_detections(detections: dict[str, object]) -> list[str]:
    """Given {source_id: SourceDetection}, return the list of IDs that
    have any trace on this machine. `available` is the strict flag, but
    we also keep adapters whose detect() noted *some* local evidence —
    typically when the detection summary mentions found files even if no
    exact payload is present (e.g. claude-desktop seeing Cache_Data).
    """
    active: list[str] = []
    for sid, detection in detections.items():
        available = getattr(detection, "available", False)
        if available:
            active.append(sid)
            continue
        # Fall back to candidate_paths: detect() often surfaces discovered
        # paths even when the source isn't "available" yet. If any path
        # exists on disk, keep this adapter in rotation so the user gets
        # the diagnose-friendly signal next time.
        candidate_paths = getattr(detection, "candidate_paths", None) or []
        for p in candidate_paths:
            try:
                if Path(str(p)).exists():
                    active.append(sid)
                    break
            except (OSError, ValueError):
                continue
    return active
