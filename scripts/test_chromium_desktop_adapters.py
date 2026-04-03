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
            {
                "kimi-desktop",
                "glm-desktop",
                "qwen-desktop",
                "deepseek-desktop",
                "doubao-desktop",
                "qianfan-desktop",
                "yuanbao-desktop",
                "perplexity-desktop",
            },
        )

    def test_glm_desktop_collects_exact_usage_from_indexeddb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            indexeddb_dir = root / "IndexedDB" / "https_chat.z.ai_0.indexeddb.leveldb"
            indexeddb_dir.mkdir(parents=True)
            indexeddb_dir.joinpath("000010.log").write_bytes(
                (
                    b"\x00https://chat.z.ai/api/v1/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T15:00:00-07:00",
                            "conversation_id": "glm-desktop-1",
                            "model": "glm-4.5",
                            "usage": {
                                "prompt_tokens": 400,
                                "completion_tokens": 100,
                                "total_tokens": 500,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "glm-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "glm-desktop-1")
        self.assertEqual(result.events[0].total_tokens, 500)
        self.assertEqual(result.events[0].raw_event_kind, "chromium_desktop:indexeddb_usage")

    def test_doubao_desktop_collects_exact_usage_from_local_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_storage_dir = root / "Local Storage" / "leveldb"
            local_storage_dir.mkdir(parents=True)
            local_storage_dir.joinpath("000003.log").write_bytes(
                (
                    b"\x00https://www.doubao.com/api/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T16:00:00-07:00",
                            "conversation_id": "doubao-1",
                            "model": "doubao-seed-1-6",
                            "usage": {
                                "prompt_tokens": 200,
                                "completion_tokens": 50,
                                "total_tokens": 250,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "doubao-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "doubao-1")
        self.assertEqual(result.events[0].total_tokens, 250)
        self.assertEqual(result.events[0].raw_event_kind, "chromium_desktop:local_storage_usage")

    def test_deepseek_desktop_collects_exact_usage_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "Cache" / "Cache_Data"
            cache_dir.mkdir(parents=True)
            cache_dir.joinpath("deadbeef_0").write_bytes(
                _cache_blob(
                    "https://api.deepseek.com/chat/completions",
                    {
                        "created_at": "2026-03-25T16:30:00-07:00",
                        "conversation_id": "deepseek-1",
                        "model": "deepseek-chat",
                        "usage": {
                            "prompt_tokens": 320,
                            "completion_tokens": 80,
                            "total_tokens": 400,
                        },
                    },
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "deepseek-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "deepseek-1")
        self.assertEqual(result.events[0].total_tokens, 400)
        self.assertEqual(result.events[0].raw_event_kind, "chromium_desktop:cache_usage")

    def test_qianfan_desktop_collects_exact_usage_from_indexeddb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            indexeddb_dir = root / "IndexedDB" / "https_wenxiaoyan.baidu.com_0.indexeddb.leveldb"
            indexeddb_dir.mkdir(parents=True)
            indexeddb_dir.joinpath("000011.log").write_bytes(
                (
                    b"\x00https://qianfan.baidubce.com/v2/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T16:40:00-07:00",
                            "conversation_id": "qianfan-1",
                            "model": "ernie-4.5-turbo-32k",
                            "usage": {
                                "prompt_tokens": 260,
                                "completion_tokens": 90,
                                "total_tokens": 350,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "qianfan-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "qianfan-1")
        self.assertEqual(result.events[0].total_tokens, 350)
        self.assertEqual(result.events[0].raw_event_kind, "chromium_desktop:indexeddb_usage")

    def test_yuanbao_desktop_collects_exact_usage_from_local_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_storage_dir = root / "Local Storage" / "leveldb"
            local_storage_dir.mkdir(parents=True)
            local_storage_dir.joinpath("000021.log").write_bytes(
                (
                    b"\x00https://yuanbao.tencent.com/api/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T16:50:00-07:00",
                            "conversation_id": "yuanbao-1",
                            "model": "hunyuan-turbos",
                            "usage": {
                                "prompt_tokens": 150,
                                "completion_tokens": 50,
                                "total_tokens": 200,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "yuanbao-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "yuanbao-1")
        self.assertEqual(result.events[0].total_tokens, 200)
        self.assertEqual(result.events[0].raw_event_kind, "chromium_desktop:local_storage_usage")

    def test_perplexity_desktop_detects_comet_root_and_indexeddb_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            indexeddb_dir = root / "IndexedDB" / "https_www.perplexity.ai_0.indexeddb.leveldb"
            indexeddb_dir.mkdir(parents=True)
            indexeddb_dir.joinpath("000020.ldb").write_bytes(
                (
                    b"\x00https://api.perplexity.ai/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T17:00:00-07:00",
                            "conversation_id": "pplx-1",
                            "model": "sonar",
                            "usage": {
                                "prompt_tokens": 180,
                                "completion_tokens": 70,
                                "reasoning_tokens": 20,
                                "total_tokens": 270,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            adapter = next(item for item in build_chromium_desktop_family_adapters() if item.source_id == "perplexity-desktop")
            adapter.root = root
            detection = adapter.detect()
            result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.status, "ready")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].session_id, "pplx-1")
        self.assertEqual(result.events[0].reasoning_tokens, 20)
        self.assertEqual(result.events[0].total_tokens, 270)


if __name__ == "__main__":
    unittest.main()
