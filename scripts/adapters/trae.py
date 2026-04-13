"""Trae AI IDE adapter.

Trae (by ByteDance) stores chat history in an encrypted SQLite database
(ModularData/ai-agent/database.db).  Without the encryption key we cannot
read per-session token counts, so this adapter reports
accuracy_level = "unsupported".

What we CAN extract without decryption:
- Installation detection  (app-data directory present + database.db exists)
- Session identifiers     (MongoDB-style ObjectIDs stored in workspace state.vscdb)
- Model names per session (ai-chat:sessionRelation:modelMap keys in state.vscdb)
- Approximate timestamps  (first 4 bytes of each ObjectID encode a Unix epoch)

These are surfaced in the SourceDetection details so that `health` and
`diagnose` give actionable output.

Recommended path for exact token data:
    python3 scripts/token_usage.py ingress serve \\
        --provider trae \\
        --upstream-base-url <your-api-endpoint> \\
        --protocol openai
Then point Trae's custom model base_url at the local proxy address.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import BaseAdapter
from core.config import TOKEN_USAGE_TRAE_ROOT_ENV, default_trae_roots, expand_path_text
from core.models import SourceCollectResult, SourceDetection, TimeWindow


_GLOBAL_STORAGE_REL = Path("User") / "globalStorage" / "state.vscdb"
_WORKSPACE_STORAGE_REL = Path("User") / "workspaceStorage"
_AGENT_DB_REL = Path("ModularData") / "ai-agent" / "database.db"
_SNAPSHOT_REL = Path("ModularData") / "ai-agent" / "snapshot"

# Keys in state.vscdb that carry session→model mappings
_MODEL_MAP_KEY_SUFFIXES = (
    "ai-chat:sessionRelation:modelMap",
    "ai-chat:sessionRelation:globalModelMap",
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _resolve_root(override: str | None = None) -> list[Path]:
    """Return candidate Trae roots, respecting env override."""
    raw = override or os.environ.get(TOKEN_USAGE_TRAE_ROOT_ENV, "").strip()
    if raw:
        return [Path(expand_path_text(raw)).expanduser()]
    return default_trae_roots()


def _objectid_to_datetime(oid_hex: str) -> datetime | None:
    """Extract the embedded Unix timestamp from a 24-char MongoDB ObjectID hex string."""
    if len(oid_hex) < 8:
        return None
    try:
        ts = int(oid_hex[:8], 16)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _read_vscdb_model_maps(db_path: Path) -> dict[str, str]:
    """Return {session_id: model_string} from a state.vscdb file."""
    if not db_path.exists():
        return {}
    result: dict[str, str] = {}
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5) as conn:
            rows = conn.execute("SELECT key, value FROM ItemTable").fetchall()
    except (sqlite3.Error, OSError):
        return {}

    for key, value in rows:
        if not isinstance(value, str):
            continue
        if not any(key.endswith(suffix) for suffix in _MODEL_MAP_KEY_SUFFIXES):
            continue
        try:
            mapping = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(mapping, dict):
            continue
        # mapping looks like: {"<session_id>": {"dev_builder": "1_-_gemini-3-pro"}}
        # or: {"<session_id>": "gemini-3-pro"}
        for session_id, model_info in mapping.items():
            if isinstance(model_info, dict):
                for model_raw in model_info.values():
                    model_str = str(model_raw).split("_-_")[-1].strip()
                    if model_str:
                        result[session_id] = model_str
                        break
            elif isinstance(model_info, str):
                model_str = model_info.split("_-_")[-1].strip()
                if model_str:
                    result[session_id] = model_str
    return result


def _read_snapshot_session_ids(snapshot_dir: Path) -> list[str]:
    """Return session IDs that have git snapshot directories."""
    if not snapshot_dir.is_dir():
        return []
    ids: list[str] = []
    try:
        for child in snapshot_dir.iterdir():
            if child.is_dir() and len(child.name) == 24:
                ids.append(child.name)
    except OSError:
        pass
    return ids


def _collect_all_session_models(root: Path) -> dict[str, str]:
    """Merge session→model mappings from global + all workspace state.vscdb files."""
    merged: dict[str, str] = {}

    # global storage
    global_db = root / _GLOBAL_STORAGE_REL
    merged.update(_read_vscdb_model_maps(global_db))

    # per-workspace storage
    ws_dir = root / _WORKSPACE_STORAGE_REL
    if ws_dir.is_dir():
        try:
            for ws in ws_dir.iterdir():
                if ws.is_dir():
                    merged.update(_read_vscdb_model_maps(ws / "state.vscdb"))
        except OSError:
            pass

    return merged


# ── adapter ────────────────────────────────────────────────────────────────────

class TraeAdapter(BaseAdapter):
    source_id = "trae"
    display_name = "Trae AI IDE"
    provider = "multi"
    accuracy_level = "unsupported"
    default_selected = True

    def _find_root(self) -> Path | None:
        for candidate in _resolve_root():
            if candidate.exists():
                return candidate
        return None

    def detect(self) -> SourceDetection:
        root = self._find_root()

        if root is None:
            return SourceDetection(
                source_id=self.source_id,
                display_name=self.display_name,
                provider=self.provider,
                accuracy_level=self.accuracy_level,
                supported=True,
                available=False,
                summary="Trae app-data directory not found",
                candidate_paths=[str(p) for p in _resolve_root()],
                details=[
                    "No Trae installation detected on this machine.",
                    f"Override search path: export {TOKEN_USAGE_TRAE_ROOT_ENV}=<path>",
                ],
            )

        agent_db = root / _AGENT_DB_REL
        snapshot_dir = root / _SNAPSHOT_REL

        session_models = _collect_all_session_models(root)
        snapshot_ids = _read_snapshot_session_ids(snapshot_dir)

        # Merge session IDs from both sources
        all_session_ids = set(session_models.keys()) | set(snapshot_ids)
        session_count = len(all_session_ids)

        # Build model summary
        model_names = sorted({m for m in session_models.values() if m})
        models_str = ", ".join(model_names) if model_names else "unknown"

        # Most recent session timestamp via ObjectID
        recent_ts: datetime | None = None
        for sid in all_session_ids:
            ts = _objectid_to_datetime(sid)
            if ts and (recent_ts is None or ts > recent_ts):
                recent_ts = ts
        recent_str = recent_ts.strftime("%Y-%m-%d") if recent_ts else "unknown"

        details = [
            f"Trae data root: {root}",
            f"Detected sessions: {session_count}",
            f"Models observed: {models_str}",
            f"Most recent session: {recent_str}",
        ]

        if agent_db.exists():
            details.append(
                f"Chat history database present ({agent_db.stat().st_size // (1024*1024)} MB) "
                "but is encrypted — token counts not accessible via direct read."
            )
            details.append(
                "To capture exact token data, route Trae through the local ingress companion:"
            )
            details.append(
                "  python3 scripts/token_usage.py ingress serve "
                "--provider trae --upstream-base-url <your-api-url> --protocol openai"
            )
        else:
            details.append("Chat history database not found; Trae may not have been used yet.")

        return SourceDetection(
            source_id=self.source_id,
            display_name=self.display_name,
            provider=self.provider,
            accuracy_level=self.accuracy_level,
            supported=True,
            available=agent_db.exists() and session_count > 0,
            summary=(
                f"Trae detected — {session_count} session(s), models: {models_str}, "
                "token counts not accessible (encrypted DB)"
            ),
            candidate_paths=[str(root)],
            details=details,
        )

    def collect(self, window: TimeWindow) -> SourceCollectResult:
        detection = self.detect()

        if not detection.available:
            return SourceCollectResult(
                detection=detection,
                events=[],
                scanned_files=0,
                verification_issues=[],
                skipped_reasons=[detection.summary],
            )

        return SourceCollectResult(
            detection=detection,
            events=[],
            scanned_files=0,
            verification_issues=[],
            skipped_reasons=[
                "Trae stores chat history in an encrypted local database. "
                "Direct token extraction is not supported. "
                "Use 'ingress serve' to capture future sessions via the local proxy."
            ],
        )
