from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


_URL_PREFIXES = (b"https://", b"http://")
_GZIP_MAGIC = b"\x1f\x8b"


@dataclass(frozen=True)
class ChromiumCacheJsonEntry:
    path: Path
    url: str
    payload: object
    body_encoding: str
    captured_at: datetime


def _cache_files(cache_dir: Path) -> list[Path]:
    if not cache_dir.exists() or not cache_dir.is_dir():
        return []
    return sorted(path for path in cache_dir.iterdir() if path.is_file())


def _extract_url(data: bytes) -> str | None:
    best_index: int | None = None
    for prefix in _URL_PREFIXES:
        index = data.find(prefix)
        if index >= 0 and (best_index is None or index < best_index):
            best_index = index
    if best_index is None:
        return None

    cursor = best_index
    while cursor < len(data):
        byte = data[cursor]
        if byte < 32 or byte > 126 or byte in {34, 39, 60, 62}:
            break
        cursor += 1
    try:
        return data[best_index:cursor].decode("utf-8")
    except UnicodeDecodeError:
        return None


def _decode_json_text(text: str) -> object | None:
    stripped = text.lstrip("\ufeff\r\n\t ")
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError:
        return None
    return payload


def _decode_gzip_payload(data: bytes, start: int) -> tuple[object | None, str | None]:
    try:
        decoded = zlib.decompress(data[start:], 16 + zlib.MAX_WBITS)
    except zlib.error:
        return None, None
    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None, None
    payload = _decode_json_text(text)
    if payload is None:
        return None, None
    return payload, "gzip"


def _decode_plain_payload(data: bytes, start: int) -> tuple[object | None, str | None]:
    try:
        text = data[start:].decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        return None, None
    payload = _decode_json_text(text)
    if payload is None:
        return None, None
    return payload, "identity"


def _extract_json_payload(data: bytes, *, url: str) -> tuple[object | None, str | None]:
    url_bytes = url.encode("utf-8", errors="ignore")
    search_start = 0
    url_index = data.find(url_bytes)
    if url_index >= 0:
        search_start = url_index + len(url_bytes)

    for offset in range(search_start, len(data) - 1):
        if data[offset : offset + 2] != _GZIP_MAGIC:
            continue
        payload, encoding = _decode_gzip_payload(data, offset)
        if payload is not None:
            return payload, encoding

    for marker in (b"{", b"["):
        cursor = search_start
        while True:
            offset = data.find(marker, cursor)
            if offset < 0:
                break
            payload, encoding = _decode_plain_payload(data, offset)
            if payload is not None:
                return payload, encoding
            cursor = offset + 1

    return None, None


def iter_json_entries(
    cache_dir: Path,
    *,
    url_keywords: tuple[str, ...] = (),
    max_files: int | None = None,
) -> Iterator[ChromiumCacheJsonEntry]:
    matched = 0
    lowered_keywords = tuple(keyword.lower() for keyword in url_keywords)
    for path in _cache_files(cache_dir):
        if max_files is not None and matched >= max_files:
            break
        try:
            data = path.read_bytes()
        except OSError:
            continue

        url = _extract_url(data)
        if not url:
            continue
        lowered_url = url.lower()
        if lowered_keywords and not any(keyword in lowered_url for keyword in lowered_keywords):
            continue

        payload, encoding = _extract_json_payload(data, url=url)
        if payload is None or encoding is None:
            continue

        matched += 1
        yield ChromiumCacheJsonEntry(
            path=path,
            url=url,
            payload=payload,
            body_encoding=encoding,
            captured_at=datetime.fromtimestamp(path.stat().st_mtime).astimezone(),
        )
