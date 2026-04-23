from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.robust_read import read_json_robust, read_text_robust  # noqa: E402


class RobustReadTests(unittest.TestCase):
    def _with_file(self, payload: bytes):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            tmp.write(payload)
            tmp.flush()
            return Path(tmp.name)
        finally:
            tmp.close()

    def test_utf8_file_decodes_without_bom(self) -> None:
        # utf-8-sig is tried first and handles both BOM-prefixed and plain
        # UTF-8 files; for a plain UTF-8 file it returns identical content
        # and reports "utf-8-sig" as the used codec (functionally correct).
        path = self._with_file("中文 token 用量".encode("utf-8"))
        text, encoding = read_text_robust(path)
        self.assertEqual(text, "中文 token 用量")
        self.assertIn(encoding, ("utf-8", "utf-8-sig"))

    def test_utf8_sig_with_bom_decodes_as_utf8_sig(self) -> None:
        content = "测试数据"
        # Explicit BOM + UTF-8 payload, avoiding any literal BOM in source.
        path = self._with_file(b"\xef\xbb\xbf" + content.encode("utf-8"))
        text, encoding = read_text_robust(path)
        self.assertEqual(text, content)
        self.assertEqual(encoding, "utf-8-sig")

    def test_gbk_file_falls_through_to_gbk(self) -> None:
        path = self._with_file("中文来源 token 用量".encode("gbk"))
        text, encoding = read_text_robust(path)
        self.assertEqual(text, "中文来源 token 用量")
        self.assertEqual(encoding, "gbk")

    def test_gb18030_only_chars_pick_gb18030(self) -> None:
        # U+1D11E (musical symbol) is in GB18030 but not GBK
        content = "音符 \U0001D11E"
        path = self._with_file(content.encode("gb18030"))
        text, encoding = read_text_robust(path)
        self.assertEqual(text, content)
        self.assertEqual(encoding, "gb18030")

    def test_big5_requires_explicit_opt_in(self) -> None:
        # Big5 is intentionally NOT in the default fallback list because GBK
        # silently "accepts" Big5 bytes and returns mojibake. Callers who
        # actually need Traditional Chinese must pass it explicitly.
        content = "繁體中文測試"
        path = self._with_file(content.encode("big5"))
        text, encoding = read_text_robust(path, encodings=("big5",))
        self.assertEqual(text, content)
        self.assertEqual(encoding, "big5")

    def test_missing_file_returns_none_tuple(self) -> None:
        text, encoding = read_text_robust(Path("/definitely/not/a/real/path-token-usage-test"))
        self.assertIsNone(text)
        self.assertIsNone(encoding)

    def test_gbk_json_parses_and_preserves_tokens(self) -> None:
        obj = {"role": "assistant", "summary": "中文内容", "tokens": {"input": 100, "output": 50}}
        path = self._with_file(json.dumps(obj, ensure_ascii=False).encode("gbk"))
        payload, encoding = read_json_robust(path)
        self.assertEqual(encoding, "gbk")
        self.assertEqual(payload["summary"], "中文内容")
        self.assertEqual(payload["tokens"]["input"], 100)
        self.assertEqual(payload["tokens"]["output"], 50)

    def test_invalid_json_across_all_codecs_returns_none(self) -> None:
        path = self._with_file(b"this is not json { broken")
        payload, encoding = read_json_robust(path)
        self.assertIsNone(payload)
        self.assertIsNone(encoding)

    def test_corrupted_bytes_fall_back_to_lossy_decode(self) -> None:
        # Byte 0xA0 alone is invalid UTF-8, invalid GBK, etc.
        # Wrap it in JSON so the replace-fallback path still yields valid JSON.
        path = self._with_file(b'{"tokens":{"input":1},"label":"\xa0\xa0"}')
        payload, encoding = read_json_robust(path)
        # Either a strict codec matched or we fell back to utf-8:replace
        self.assertIsNotNone(payload)
        self.assertEqual(payload["tokens"]["input"], 1)


if __name__ == "__main__":
    unittest.main()
