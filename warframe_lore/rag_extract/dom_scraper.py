"""Playwright (DOM) fallback extraction for client-rendered pages.

Single responsibility: when the Wikitext path fails (or is not viable),
load the page in a headless browser, expand dynamic blocks (``.spoiler``,
``.expand-button``) and rebuild a sectioned Markdown document.  The
Playwright dependency is imported lazily so the primary (Wikitext) path
never requires a browser installation.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from typing import Any

import aiohttp

from .extractors import ExtractedPage, _title_from_url
from .resilience import retry_when

logger = logging.getLogger(__name__)


def _is_transient_network_error(exc: BaseException) -> bool:
    """Retry predicate covering aiohttp, timeouts and Playwright errors."""
    if isinstance(exc, (aiohttp.ClientError, OSError, asyncio.TimeoutError)):
        return True
    try:
        from playwright.async_api import Error as PlaywrightError

        return isinstance(exc, PlaywrightError)
    except ImportError:  # pragma: no cover - Playwright not installed
        return False


class PlaywrightFallbackExtractor:
    """Headless-browser fallback for client-rendered pages.

    Loads the page, expands dynamic blocks (``.spoiler``, ``.expand-button``)
    and walks the DOM to rebuild a sectioned Markdown document. The
    Playwright dependency is imported lazily so the primary (Wikitext) path
    never requires a browser installation.
    """

    def __init__(
        self, *, wait_until: str = "networkidle", timeout_millis: int = 45000
    ) -> None:
        self._wait_until = wait_until
        self._timeout_millis = timeout_millis

        if importlib.util.find_spec("playwright") is None:  # pragma: no cover
            raise ImportError(
                "Playwright n'est pas installé: pip install playwright "
                "puis 'playwright install chromium'."
            )

    @retry_when(_is_transient_network_error)
    async def extract(self, url: str) -> ExtractedPage:
        """Load ``url`` headless, expand dynamic blocks and scrape the DOM."""
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(
                    url, wait_until=self._wait_until,
                    timeout=self._timeout_millis)
                await _expand_dynamic_blocks(page)

                page_title = await _dom_page_title(page, url)
                text = await _dom_to_markdown(page, page_title)
                logger.info(
                    "DOM scraped for '%s' (%d chars)", page_title, len(text)
                )
                return ExtractedPage(source_url=url, page_title=page_title, text=text)
            finally:
                await browser.close()


async def _expand_dynamic_blocks(page: Any) -> None:
    """Click every collapsible element so hidden content gets scraped."""
    for selector in (".spoiler", ".expand-button", "button.expand"):
        elements = await page.query_selector_all(selector)
        for element in elements:
            try:
                await element.click(timeout=1500)
            except Exception:  # noqa: BLE001 - non-blocking interaction
                continue


async def _dom_page_title(page: Any, fallback_url: str) -> str:
    """Page title: prefer the ``h1`` heading, fall back to the document title."""
    h1 = page.locator("h1").first
    if await h1.count():
        title = (await h1.text_content() or "").strip()
        if title:
            return title
    return _title_from_url(fallback_url)


async def _dom_to_markdown(page: Any, page_title: str) -> str:
    """Rebuild a sectioned Markdown document from the rendered DOM.

    Each semantic block (H2/H3 plus the text that follows it) is emitted
    with a Markdown heading so the chunking step can reuse the same
    splitting logic as the Wikitext path.
    """
    blocks = await page.evaluate(
        """() => {
            const out = [];
            const headings = document.querySelectorAll('h1, h2, h3');
            for (const heading of headings) {
                let body = '';
                let node = heading.nextElementSibling;
                while (node && !/^h[1-6]$/i.test(node.tagName)) {
                    if (node.innerText) body += node.innerText + '\\n';
                    node = node.nextElementSibling;
                }
                out.push({
                    tag: heading.tagName.toLowerCase(),
                    title: (heading.innerText || '').trim(),
                    body: body.trim()
                });
            }
            return out;
        }"""
    )

    lines: list[str] = []
    lead_bits: list[str] = []
    for block in blocks:
        level = len(block["tag"])  # h2 -> 2, h3 -> 3
        if level < 2:
            if block.get("body"):
                lead_bits.append(block["body"])
            continue
        if lead_bits:
            lines.append(lead_bits.pop(0))
        title = block.get("title")
        if title:
            lines.append(f"\n{'#' * level} {title}\n")
        if block.get("body"):
            lines.append(block["body"])
    if lead_bits and not lines:
        lines.append(lead_bits.pop(0))
    text = "\n".join(lines).strip()
    return text if text else page_title
