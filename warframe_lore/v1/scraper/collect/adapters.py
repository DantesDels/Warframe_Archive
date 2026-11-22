"""Source adapters for v1 collection."""

from __future__ import annotations

import lzma
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .html_extract import extract_links, html_title, html_to_text
from .http import HttpClient, bot_headers, browser_headers


@dataclass(slots=True)
class CollectedPage:
    title: str
    url: str
    content: str


def collect_pages(
    source: dict, client: HttpClient, limits: dict
) -> list[CollectedPage]:
    location = str(source.get("location", "")).strip()
    kind = str(source.get("kind", "website"))
    if kind == "document" or Path(location).exists():
        return [_collect_file(location)]
    return _collect_url(location, client, limits)


def _collect_file(location: str) -> CollectedPage:
    path = Path(location)
    text = path.read_text(encoding="utf-8", errors="replace")
    return CollectedPage(title=path.name, url=str(path), content=text)


def _collect_url(url: str, client: HttpClient, limits: dict) -> list[CollectedPage]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "wiki" in host and "/api.php" not in parsed.path:
        return _collect_mediawiki(url, client, limits)
    if url.lower().endswith(".lzma"):
        return [_collect_lzma(url, client)]
    return _collect_html(url, client, limits)


def _collect_lzma(url: str, client: HttpClient) -> CollectedPage:
    resp = client.get(url, headers=browser_headers())
    text = _decode_lzma(resp.content)
    title = Path(urlparse(resp.url).path).name or urlparse(resp.url).netloc
    return CollectedPage(title=title, url=resp.url, content=text)


def _collect_html(url: str, client: HttpClient, limits: dict) -> list[CollectedPage]:
    max_pages = max(1, int(limits.get("max_pages_per_source", 1)))
    max_depth = max(0, int(limits.get("max_depth", 0)))
    same_host = bool(limits.get("same_host_only", True))
    queue: list[tuple[str, int]] = [(url, 0)]
    seen: set[str] = set()
    pages: list[CollectedPage] = []
    while queue and len(pages) < max_pages:
        current, depth = queue.pop(0)
        norm = current.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        resp = client.get(current, headers=browser_headers())
        ctype = resp.content_type.lower()
        body = resp.content.decode(resp.encoding or "utf-8", errors="replace")
        if "html" not in ctype and "<html" not in body.lower():
            title = Path(urlparse(resp.url).path).name or urlparse(resp.url).netloc
            pages.append(CollectedPage(title=title, url=resp.url, content=body))
            continue
        title = html_title(body) or urlparse(resp.url).netloc
        content = html_to_text(body)
        pages.append(CollectedPage(title=title, url=resp.url, content=content))
        if depth >= max_depth:
            continue
        for link in extract_links(body, resp.url, same_host=same_host):
            if link.rstrip("/") not in seen:
                queue.append((link, depth + 1))
    return pages


def _collect_mediawiki(
    url: str, client: HttpClient, limits: dict
) -> list[CollectedPage]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    api = f"{base}/api.php"
    max_pages = max(1, int(limits.get("max_pages_per_source", 1)))
    title = parse_qs(parsed.query).get("title", [None])[0]
    if not title:
        tail = parsed.path.rsplit("/", 1)[-1].replace("_", " ").strip()
        title = tail or "Main Page"
    pages = _mw_extract(client, api, title)
    if pages:
        return pages[:max_pages]
    if max_pages <= 1:
        return [_mw_single_html(url, client)]
    discovered = _mw_all_pages(client, api, max_pages=max_pages)
    results: list[CollectedPage] = []
    for page_title in discovered[:max_pages]:
        results.extend(_mw_extract(client, api, page_title))
    return results or [_mw_single_html(url, client)]


def _mw_single_html(url: str, client: HttpClient) -> CollectedPage:
    resp = client.get(url, headers=browser_headers())
    body = resp.content.decode(resp.encoding or "utf-8", errors="replace")
    return CollectedPage(html_title(body) or url, resp.url, html_to_text(body))


def _mw_extract(client: HttpClient, api: str, title: str) -> list[CollectedPage]:
    params = {
        "action": "query", "prop": "extracts|info", "explaintext": 1,
        "inprop": "url", "redirects": 1, "titles": title, "format": "json",
    }
    try:
        resp = client.get(api, headers=bot_headers(), params=params)
    except Exception:
        resp = client.get(api, headers=browser_headers(), params=params)
    data = _json(resp.content)
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    text = str(page.get("extract", "") or "").strip()
    if not text:
        return []
    return [CollectedPage(
        title=str(page.get("title", title)),
        url=str(page.get("fullurl", title)),
        content=text,
    )]


def _mw_all_pages(client: HttpClient, api: str, *, max_pages: int) -> list[str]:
    titles: list[str] = []
    apcontinue = None
    while len(titles) < max_pages:
        params = {
            "action": "query", "list": "allpages", "apnamespace": "0",
            "aplimit": str(min(50, max_pages - len(titles))), "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        try:
            resp = client.get(api, headers=bot_headers(), params=params)
        except Exception:
            resp = client.get(api, headers=browser_headers(), params=params)
        data = _json(resp.content)
        for item in data.get("query", {}).get("allpages", []):
            page_title = str(item.get("title", "")).strip()
            if page_title:
                titles.append(page_title)
        cont = data.get("continue", {}).get("apcontinue")
        if not cont:
            break
        apcontinue = cont
    return titles


def _decode_lzma(data: bytes) -> str:
    try:
        return lzma.decompress(data).decode("utf-8", errors="replace")
    except lzma.LZMAError:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        out = bytearray()
        for i in range(0, len(data), 64):
            try:
                out.extend(dec.decompress(data[i:i + 64], max_length=1 << 20))
            except lzma.LZMAError:
                break
            if dec.eof:
                break
        if not out:
            raise
        return out.decode("utf-8", errors="replace")


def _json(data: bytes) -> dict:
    import json

    return json.loads(data.decode("utf-8", errors="replace"))
