"""Source collection helpers for execution worker."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def collect_source(
    source: dict, universe_id: str
) -> tuple[dict | None, str | None]:
    loc = str(source.get("location", "")).strip()
    kind = source.get("kind", "website")
    try:
        text, title, url = _read_source(loc, kind)
        text = " ".join(text.split())[:20_000]
        if not text:
            return None, f"{loc}: contenu vide"
        doc = {
            "id": _doc_id(source),
            "universeId": universe_id,
            "sourceId": source.get("id"),
            "title": title[:180],
            "url": url,
            "docType": kind,
            "language": "fr",
            "relevance": float(source.get("score", 1.0)),
            "isDuplicate": False,
            "excerpt": text[:280],
            "content": text,
        }
        return doc, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{loc}: {exc}"


def _doc_id(source: dict) -> str:
    suffix = int(time.time() * 1000) % 100000
    return f"doc-{source.get('id', 'src')}-{suffix}"


def _read_source(loc: str, kind: str) -> tuple[str, str, str]:
    if kind == "document" or Path(loc).exists():
        text = Path(loc).read_text(encoding="utf-8", errors="replace")
        return text, Path(loc).name, str(Path(loc))
    req = Request(loc, headers={"User-Agent": "AtelierV1/1.0"})
    with urlopen(req, timeout=15) as resp:  # noqa: S310
        raw = resp.read(200_000)
        ctype = resp.headers.get("Content-Type", "")
        text = raw.decode("utf-8", errors="replace")
    title = _title_from_html(text) or urlparse(loc).netloc or loc
    if "html" in ctype.lower() or "<html" in text.lower():
        text = _strip_html(text)
    return text, title, loc


def _title_from_html(html: str) -> str:
    low = html.lower()
    start = low.find("<title>")
    end = low.find("</title>")
    if start != -1 and end != -1 and end > start:
        return _strip_html(html[start + 7:end]).strip()[:180]
    return ""


def _strip_html(text: str) -> str:
    out, in_tag = [], False
    for ch in text:
        if ch == "<":
            in_tag = True
            out.append(" ")
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            out.append(ch)
    return "".join(out)
