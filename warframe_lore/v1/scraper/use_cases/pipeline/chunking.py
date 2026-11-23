"""Structure-aware chunking for RAG export."""

from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6}\s+.+|[A-Z][^\n]{0,80}:)$")


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    clean = (text or "").strip()
    if not clean:
        return []
    blocks = _split_blocks(clean)
    chunks: list[str] = []
    buf = ""
    current_heading = ""
    for block in blocks:
        if _HEADING.match(block):
            current_heading = block.strip()
        candidate = _join(buf, block)
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf.strip())
        prefixed = (
            _join(current_heading, block)
            if current_heading and current_heading not in block
            else block
        )
        if len(prefixed) <= max_chars:
            buf = prefixed
        else:
            chunks.extend(_split_long(prefixed, max_chars=max_chars, overlap=overlap))
            buf = ""
    if buf:
        chunks.append(buf.strip())
    out = [c for c in chunks if c]
    return _dedupe_adjacent(out)


def _split_blocks(text: str) -> list[str]:
    # keep headings and paragraphs as structure units
    raw = re.split(r"\n{2,}", text)
    blocks: list[str] = []
    for part in raw:
        part = part.strip()
        if not part:
            continue
        lines = [ln.rstrip() for ln in part.splitlines() if ln.strip()]
        for line in lines:
            blocks.append(line.strip())
        if len(lines) > 1 and not any(_HEADING.match(ln.strip()) for ln in lines):
            blocks[-len(lines):] = ["\n".join(lines)]
    return blocks


def _join(a: str, b: str) -> str:
    if not a:
        return b.strip()
    return f"{a.rstrip()}\n\n{b.strip()}".strip()


def _split_long(text: str, *, max_chars: int, overlap: int) -> list[str]:
    # sentence-aware split fallback
    parts = re.split(r"(?<=[\.!?]\s)\s+|\n+", text)
    parts = [p.strip() for p in parts if p.strip()]
    chunks: list[str] = []
    buf = ""
    for part in parts:
        if len(part) > max_chars:
            if buf:
                chunks.append(buf.strip())
                buf = ""
            start = 0
            while start < len(part):
                end = min(len(part), start + max_chars)
                chunks.append(part[start:end].strip())
                if end >= len(part):
                    break
                start = max(end - overlap, start + 1)
            continue
        cand = _join(buf, part)
        if len(cand) <= max_chars:
            buf = cand
        else:
            if buf:
                chunks.append(buf.strip())
            buf = part
    if buf:
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def _dedupe_adjacent(chunks: list[str]) -> list[str]:
    out: list[str] = []
    for c in chunks:
        if not out or out[-1] != c:
            out.append(c)
    return out
