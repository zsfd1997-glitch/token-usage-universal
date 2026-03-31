from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from core.config import TOKEN_USAGE_CACHE_ROOT_ENV
from core.models import UsageEvent


_CACHE_VERSION = 1


def _default_cache_root() -> Path:
    raw = os.environ.get(TOKEN_USAGE_CACHE_ROOT_ENV, "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    return Path.home() / ".codex" / "cache" / "token-usage-universal"


def _event_from_dict(payload: dict[str, object]) -> UsageEvent:
    return UsageEvent.from_dict(payload)


class FileEventCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_cache_root()).expanduser()

    def _entry_path(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        kind: str = "events",
        extra_key: str = "",
    ) -> Path:
        digest = hashlib.sha1(f"{kind}:{parser_version}:{extra_key}:{path.resolve()}".encode("utf-8")).hexdigest()
        return self.root / source_id / f"{digest}.json"

    @staticmethod
    def _signature(path: Path) -> dict[str, object] | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return {
            "path": str(path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    def _load_entries(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        kind: str,
        extra_key: str = "",
    ) -> tuple[list[UsageEvent], list[str]] | None:
        signature = self._signature(path)
        if signature is None:
            return None

        entry_path = self._entry_path(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            kind=kind,
            extra_key=extra_key,
        )
        if not entry_path.exists():
            return None

        try:
            payload = json.loads(entry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if payload.get("cache_version") != _CACHE_VERSION:
            return None
        if payload.get("kind") != kind:
            return None
        if payload.get("parser_version") != parser_version:
            return None
        if payload.get("source_id") != source_id:
            return None
        if payload.get("extra_key", "") != extra_key:
            return None
        if payload.get("signature") != signature:
            return None

        events = [_event_from_dict(item) for item in payload.get("events", [])]
        issues = [str(item) for item in payload.get("verification_issues", [])]
        return events, issues

    def load(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
    ) -> tuple[list[UsageEvent], list[str]] | None:
        return self._load_entries(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            kind="events",
        )

    def load_day_rollups(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        timezone_name: str,
    ) -> tuple[list[UsageEvent], list[str]] | None:
        return self._load_entries(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            kind="day-rollup",
            extra_key=timezone_name,
        )

    def _save_entries(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        events: list[UsageEvent],
        verification_issues: list[str],
        kind: str,
        extra_key: str = "",
    ) -> None:
        signature = self._signature(path)
        if signature is None:
            return

        entry_path = self._entry_path(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            kind=kind,
            extra_key=extra_key,
        )
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_version": _CACHE_VERSION,
            "kind": kind,
            "source_id": source_id,
            "parser_version": parser_version,
            "extra_key": extra_key,
            "signature": signature,
            "events": [event.as_dict() for event in events],
            "verification_issues": verification_issues,
        }
        fd, temp_name = tempfile.mkstemp(
            prefix=f"{entry_path.stem}.",
            suffix=".tmp",
            dir=str(entry_path.parent),
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            temp_path.replace(entry_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def save(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        events: list[UsageEvent],
        verification_issues: list[str],
    ) -> None:
        self._save_entries(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            events=events,
            verification_issues=verification_issues,
            kind="events",
        )

    def save_day_rollups(
        self,
        *,
        source_id: str,
        parser_version: str,
        path: Path,
        timezone_name: str,
        events: list[UsageEvent],
        verification_issues: list[str],
    ) -> None:
        self._save_entries(
            source_id=source_id,
            parser_version=parser_version,
            path=path,
            events=events,
            verification_issues=verification_issues,
            kind="day-rollup",
            extra_key=timezone_name,
        )
