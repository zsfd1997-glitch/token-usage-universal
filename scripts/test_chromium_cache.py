from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.chromium_cache import iter_json_entries


def _cache_blob(url: str, payload: object, *, gzip_body: bool) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    if gzip_body:
        body = gzip.compress(body)
    return (b"\x00" * 28) + f"1/0/{url}".encode("utf-8") + b"\x00\x00" + body


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


if __name__ == "__main__":
    unittest.main()
