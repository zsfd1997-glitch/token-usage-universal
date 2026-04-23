"""Robust file reading for third-party AI client data.

Third-party clients (OpenCode, Claude Code, Kimi CLI, Gemini CLI, etc.)
write their own session / message JSON under the user's home directory.
Most of the time these are strict UTF-8, but intranet Windows hosts with
a GBK (cp936) system codepage have been observed producing mojibake or
files partially encoded in the legacy codec — either because the tool
itself called unguarded `open()` / `os.write()` in the default codec,
or because a user edited files with a non-UTF-8 text editor.

Silent `UnicodeDecodeError` swallowing turns this into a zero-token bug
that's impossible to diagnose from the outside: the adapter scans N
files, gets None for every one, and reports "0 events" with no warning.

This module provides two helpers that try a short list of codecs before
giving up, and a diagnostic fallback that always returns SOMETHING so
token-bearing structure survives even partial corruption.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_TEXT_ENCODINGS: tuple[str, ...] = (
    # utf-8-sig first: it strips a BOM if present (common from Windows
    # Notepad) and otherwise behaves identically to plain utf-8. Putting
    # it ahead of "utf-8" means BOM-prefixed files don't end up with a
    # stray U+FEFF char in the decoded text.
    "utf-8-sig",
    # Plain UTF-8 for belt-and-suspenders (functionally covered by
    # utf-8-sig, but explicit about the success encoding reported back).
    "utf-8",
    # Simplified Chinese mainland intranet (Windows cp936 / zh_CN.GBK locale).
    # GBK is a subset of GB18030, so try GBK first for strict match, then
    # GB18030 which handles rare 4-byte chars missing from GBK.
    "gbk",
    "gb18030",
)

# Note on Big5 / Shift-JIS / EUC-KR: we deliberately do NOT add them to the
# default fallback list. GBK / GB18030 accept nearly any 2-byte sequence in
# the 0x81-0xFE range without raising UnicodeDecodeError, so a Big5-encoded
# file would "succeed" as GBK but decode into nonsensical characters. Since
# our primary intranet target is Simplified Chinese (mainland China, GBK/
# cp936), we optimize for that case. Callers who need CJK-Traditional or
# Japanese decoding can pass `encodings=("big5",)` explicitly.


def read_text_robust(
    path: Path,
    *,
    encodings: tuple[str, ...] = DEFAULT_TEXT_ENCODINGS,
) -> tuple[str | None, str | None]:
    """Return (text, encoding_used) or (None, None).

    Tries each candidate encoding in order. Never raises; caller gets
    a concrete None when the file is unreadable or no codec fits.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None, None

    for encoding in encodings:
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    try:
        return raw_bytes.decode("utf-8", errors="replace"), "utf-8:replace"
    except UnicodeDecodeError:
        return None, None


def read_json_robust(
    path: Path,
    *,
    encodings: tuple[str, ...] = DEFAULT_TEXT_ENCODINGS,
) -> tuple[Any, str | None]:
    """Return (parsed_json, encoding_used) or (None, None).

    Tries each candidate encoding in order; the first codec that produces
    valid JSON wins. If no codec produces valid JSON the file is
    considered unreadable — silently swallowed by default, callers that
    want to flag it can check encoding_used == None.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return None, None

    for encoding in encodings:
        try:
            text = raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        try:
            return json.loads(text), encoding
        except json.JSONDecodeError:
            continue

    # Last resort: decode with replace so at least token-bearing integer
    # fields survive when only a string field is corrupted.
    try:
        text = raw_bytes.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return None, None
    try:
        return json.loads(text), "utf-8:replace"
    except json.JSONDecodeError:
        return None, None
