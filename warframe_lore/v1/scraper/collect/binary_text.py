"""Safe binary-to-text conversion for compressed and local payloads."""

from __future__ import annotations

import lzma
import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")


def decode_lzma(data: bytes) -> str:
    """Decompress an ALONE/AUTO LZMA payload into sanitized UTF-8 text."""
    try:
        raw = lzma.decompress(data)
    except lzma.LZMAError:
        raw = _decompress_alone(data)
    return safe_text(raw)


def safe_text(data: bytes) -> str:
    """Decode bytes with strict codecs before falling back to replacement."""
    for encoding in _ENCODINGS:
        try:
            return sanitize(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return sanitize(data.decode("utf-8", errors="replace"))


def sanitize(text: str) -> str:
    """Remove control characters that corrupt text corpora."""
    return _CONTROL.sub("", text)


def looks_binary(text: str) -> bool:
    """Reject payloads that still contain binary control bytes or replacements."""
    sample = text[:2000]
    if not sample:
        return False
    control = sum(1 for char in sample if ord(char) < 32 and char not in "\n\r\t")
    return control > 0 or "\ufffd" in sample


def _decompress_alone(data: bytes) -> bytes:
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    output = bytearray()
    try:
        for offset in range(0, len(data), 64):
            chunk = data[offset:offset + 64]
            if not chunk:
                break
            output.extend(decoder.decompress(chunk, max_length=1 << 20))
            if decoder.eof:
                break
    except lzma.LZMAError:
        pass
    if not output:
        raise ValueError("invalid LZMA payload")
    return bytes(output)
