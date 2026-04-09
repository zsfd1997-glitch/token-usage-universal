from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.chromium_cache import iter_json_entries, iter_leveldb_json_entries


_ZSTD_CLI = shutil.which("zstd")
_BROTLI_CLI = shutil.which("brotli")


def _compress_with_cli(command: str | None, args: list[str], payload: bytes) -> bytes:
    if command is None:
        raise unittest.SkipTest(f"{args[0]} CLI not available on this machine")
    result = subprocess.run(
        [command, *args[1:]],
        input=payload,
        capture_output=True,
        check=False,
    )
    if not result.stdout:
        raise unittest.SkipTest(f"{args[0]} CLI did not produce compressed output")
    return result.stdout


def _cache_blob(
    url: str,
    payload: object,
    *,
    gzip_body: bool = False,
    zstd_body: bool = False,
    brotli_body: bool = False,
    plain_prefix: bytes = b"",
    separator: bytes | None = None,
) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    if gzip_body:
        body = gzip.compress(body)
    elif zstd_body:
        body = _compress_with_cli(_ZSTD_CLI, ["zstd", "-q", "-c"], body)
    elif brotli_body:
        body = _compress_with_cli(_BROTLI_CLI, ["brotli", "-c"], body)

    blob = (b"\x00" * 28) + f"1/0/{url}".encode("utf-8")
    if plain_prefix:
        blob += b"\x00" + plain_prefix
    if separator is None:
        separator = b"\x00\x00"
    if brotli_body:
        return blob + b"\x00" + body + b"\x00content-encoding:br\x00\x00"
    return blob + separator + body


class ChromiumCacheTests(unittest.TestCase):
    def test_iter_json_entries_decodes_gzip_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "deadbeef_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://agent.minimax.io/api/v1/chat/completions",
                    {"requestID": "req-1", "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}},
                    gzip_body=True,
                )
            )

            entries = list(iter_json_entries(cache_dir, url_keywords=("agent.minimax.io",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].body_encoding, "gzip")
        self.assertEqual(entries[0].payload["requestID"], "req-1")
        self.assertEqual(entries[0].payload["usage"]["total_tokens"], 150)

    def test_iter_json_entries_decodes_zstd_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "c001d00d_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://claude.ai/api/organizations/org/chat_conversations/conv-1",
                    {"id": "conv-1", "messages": [{"role": "user", "text": "hi"}]},
                    zstd_body=True,
                    plain_prefix=b"{}",
                )
            )

            entries = list(iter_json_entries(cache_dir, url_keywords=("claude.ai/api/",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].body_encoding, "zstd")
        self.assertEqual(entries[0].payload["id"], "conv-1")

    def test_iter_json_entries_trims_trailing_frame_byte_from_url_before_zstd_decode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "c10def00_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://claude.ai/api/organizations/org/chat_conversations/conv-2?consistency=eventual",
                    {"id": "conv-2", "usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}},
                    zstd_body=True,
                    separator=b"",
                )
            )

            entries = list(iter_json_entries(cache_dir, url_keywords=("claude.ai/api/",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].url, "https://claude.ai/api/organizations/org/chat_conversations/conv-2?consistency=eventual")
        self.assertEqual(entries[0].body_encoding, "zstd")
        self.assertEqual(entries[0].payload["usage"]["total_tokens"], 150)

    def test_iter_json_entries_decodes_brotli_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "b01df00d_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://agent.minimax.io/v1/api/user/info",
                    {"statusInfo": {"code": 0}, "data": {"userID": "user-1"}},
                    brotli_body=True,
                )
            )

            entries = list(iter_json_entries(cache_dir, url_keywords=("agent.minimax.io",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].body_encoding, "br")
        self.assertEqual(entries[0].payload["data"]["userID"], "user-1")

    def test_iter_json_entries_decodes_plain_json_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "feedface_0"
            cache_file.write_bytes(
                _cache_blob(
                    "https://agent.minimax.io/api/v1/user/info",
                    {"status": "ok", "userID": "user-1"},
                    gzip_body=False,
                )
            )

            entries = list(iter_json_entries(cache_dir, url_keywords=("agent.minimax.io",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].body_encoding, "identity")
        self.assertEqual(entries[0].payload["userID"], "user-1")

    def test_iter_leveldb_json_entries_decodes_json_from_leveldb_like_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_dir = Path(tmp)
            store_dir.joinpath("000004.log").write_bytes(
                (
                    b"\x00leveldb-prefix https://chat.z.ai/api/v1/chat/completions\x00"
                    + json.dumps(
                        {
                            "created_at": "2026-03-25T12:00:00-07:00",
                            "conversation_id": "glm-1",
                            "usage": {
                                "prompt_tokens": 240,
                                "completion_tokens": 60,
                                "total_tokens": 300,
                            },
                        }
                    ).encode("utf-8")
                )
            )

            entries = list(iter_leveldb_json_entries(store_dir, text_keywords=("chat.z.ai/api/",)))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].body_encoding, "leveldb-json")
        self.assertEqual(entries[0].payload["conversation_id"], "glm-1")
        self.assertEqual(entries[0].payload["usage"]["total_tokens"], 300)


if __name__ == "__main__":
    unittest.main()
