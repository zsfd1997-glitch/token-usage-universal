from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.chromium_desktop_family import build_chromium_desktop_family_adapters
from adapters.claude_desktop import ClaudeDesktopAdapter
from core.models import TimeWindow


def _window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


def _cache_blob(url: str, payload: object) -> bytes:
    return (b"\x00" * 28) + f"1/0/{url}".encode("utf-8") + b"\x00" + gzip.compress(json.dumps(payload).encode("utf-8"))


class ChromiumDesktopAdapterTests(unittest.TestCase):
    def test_claude_desktop_detects_and_collects_exact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_dir.joinpath("cafebabe_0").write_bytes(
                _cache_blob(
                    "https://api.anthropic.com/v1/messages",
                    {
                        "created_at": "2026-03-25T12:00:00-07:00",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-5",
                        "conversation_id": "cld-1",
                        "usage": {
                            "input_tokens": 500,
                            "cache_read_input_tokens": 40,
                            "output_tokens": 120,
                            "total_tokens": 620,
                        },
                    },
                )
            )

            adapter = ClaudeDesktopAdapter(root=root)
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "cld-1")
        self.assertEqual(result.events[0].total_tokens, 620)
        self.assertEqual(result.events[0].cached_input_tokens, 40)
        self.assertEqual(result.events[0].raw_model, "claude-sonnet-4-5")

    def test_claude_desktop_reports_traces_without_exact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            indexeddb_dir = root / "IndexedDB" / "https_claude.ai_0.indexeddb.leveldb"
            indexeddb_dir.mkdir(parents=True)
            indexeddb_dir.joinpath("000004.log").write_text("conversation cache marker", encoding="utf-8")
            cache_dir.joinpath("feedface_0").write_bytes(
                _cache_blob(
                    "https://api.anthropic.com/mcp-registry/v0/servers?version=latest",
                    {"servers": [{"server": {"name": "demo"}}]},
                )
            )

            detection = ClaudeDesktopAdapter(root=root).detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("desktop traces detected", detection.summary)
        self.assertTrue(any("IndexedDB" in detail for detail in detection.details))

    def test_family_builder_exposes_independent_desktop_sources(self) -> None:
        source_ids = {adapter.source_id for adapter in build_chromium_desktop_family_adapters()}

        self.assertEqual(
            source_ids,
            {"kimi-desktop", "glm-desktop", "qwen-desktop", "doubao-desktop", "perplexity-desktop"},
        )


if __name__ == "__main__":
    unittest.main()
