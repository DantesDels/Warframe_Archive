"""LZMA decompression tolerant of truncated streams."""

from __future__ import annotations

import lzma
import logging

log = logging.getLogger(__name__)


def decompress_lzma(data: bytes) -> str:
    """Decompresses an ``FORMAT_ALONE`` LZMA stream, tolerating truncation.

    The official server sometimes serves a shortened index (missing
    LZMA end-of-stream marker).  In that case we return the already-decoded
    beginning (valid hashed names) and log a warning.
    """
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    out = bytearray()
    position = 0
    while position < len(data) and not decompressor.eof:
        try:
            # Small chunks: if the stream is truncated mid-packet,
            # we keep as much valid data already decoded as possible.
            out.extend(decompressor.decompress(
                data[position:position + 64], max_length=1 << 20))
        except lzma.LZMAError:
            log.warning("Partial LZMA index: ended before stream end "
                        "(decoded %d bytes out of %d).", len(out), len(data))
            break
        position += 64
    return out.decode("utf-8", errors="replace")
