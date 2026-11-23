"""Generic headless Playwright renderer for dynamic JS/SPA catalog pages."""

from __future__ import annotations

import importlib.util
import threading
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from .crawl_filter import keep_crawl_url

_BROWSER_SEM = threading.Semaphore(2)

_SPA_MARKERS = (
    "__next_data__",
    "__nuxt__",
    'id="__next"',
    'id="app"',
    'id="root"',
    "data-v-app",
    "ng-version",
    'type="module"',
)
_SAFE_TAB_SELECTOR = '[role="tab"]:not([aria-disabled="true"])'


@dataclass(slots=True)
class SpaRenderResult:
    """Rendered DOM, resolved URL, links and same-host JSON API endpoints."""

    final_url: str
    title: str
    html: str
    links: list[str] = field(default_factory=list)
    json_endpoints: list[str] = field(default_factory=list)


def playwright_available() -> bool:
    """Return True when the optional playwright package is installed."""
    return importlib.util.find_spec("playwright") is not None


def looks_like_spa(html: str, static_link_count: int) -> bool:
    """Detect JS-rendered catalog pages that need headless browser execution."""
    if not html:
        return False
    low = html.lower()
    return any(m in low for m in _SPA_MARKERS) and static_link_count < 25


def _root_domain(host: str) -> str:
    parts = [p for p in host.lower().removeprefix("www.").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def render_spa_page(
    url: str, *, timeout_ms: int = 25000, scroll_steps: int = 3, click_tabs: bool = True
) -> SpaRenderResult:
    """Render a JS/SPA page in headless Chromium and collect all catalog links."""
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

    base_domain = _root_domain(urlparse(url).hostname or "")
    json_urls: list[str] = []
    seen_json: set[str] = set()
    links: list[str] = []
    seen_links: set[str] = set()
    with _BROWSER_SEM, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.on(
                "response",
                lambda r: _capture_json(r, base_domain, json_urls, seen_json),
            )
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_timeout(800)
            _scroll_page(page, scroll_steps)
            _collect_dom_links(page, links, seen_links)
            if click_tabs:
                _explore_tabs(page, links, seen_links)
            final_url = page.url or url
            title = page.title() or final_url
            html = page.content()
        finally:
            browser.close()
    return SpaRenderResult(final_url, title, html, links, json_urls)


def _capture_json(
    response: Any, base_domain: str, out: list[str], seen: set[str]
) -> None:
    try:
        ct = str((response.headers or {}).get("content-type", "")).lower()
        if response.status != 200 or "json" not in ct:
            return
        host = urlparse(response.url).hostname or ""
        if base_domain and _root_domain(host) != base_domain:
            return
        if response.url not in seen:
            seen.add(response.url)
            out.append(response.url)
    except Exception:  # noqa: BLE001
        return


def _scroll_page(page: Any, steps: int) -> None:
    for _ in range(max(0, steps)):
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            page.wait_for_timeout(350)
        except Exception:  # noqa: BLE001
            break


def _collect_dom_links(page: Any, out: list[str], seen: set[str]) -> None:
    try:
        hrefs = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href || '')"
        )
    except Exception:  # noqa: BLE001
        return
    base = page.url or ""
    for raw in hrefs or []:
        url = urljoin(base, str(raw).strip()).split("#", 1)[0]
        norm = url.rstrip("/").lower()
        if (
            not url.startswith(("http://", "https://"))
            or norm in seen
            or not keep_crawl_url(url, base)
        ):
            continue
        seen.add(norm)
        out.append(url)


def _explore_tabs(page: Any, out: list[str], seen: set[str]) -> None:
    try:
        tabs = page.locator(_SAFE_TAB_SELECTOR)
        for idx in range(min(6, tabs.count())):
            tab = tabs.nth(idx)
            if tab.is_visible():
                tab.click(timeout=1500)
                page.wait_for_timeout(450)
                _collect_dom_links(page, out, seen)
    except Exception:  # noqa: BLE001
        return
