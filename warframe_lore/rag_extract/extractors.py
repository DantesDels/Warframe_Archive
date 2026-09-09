"""Extraction strategies for the decoupled RAG pipeline.

``BaseExtractor`` defines the strategy contract; ``MediaWikiExtractor`` is
the primary strategy (Wikitext via the Fandom MediaWiki API), and
``PlaywrightFallbackExtractor`` a DOM fallback for pages whose content is
rendered client-side.

Every network call is wrapped with a Tenacity retry policy (3 attempts,
exponential backoff) defined in the ``resilience`` helpers.
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp
import mwparserfromhell

from .resilience import retry_network, retry_when

logger = logging.getLogger(__name__)

DEFAULT_API_ENDPOINT = "https://warframe.fandom.com/api.php"
DEFAULT_USER_AGENT = "WarframeArchives-RAGPipeline/1.0 (aiohttp + mwparserfromhell)"
URL_TITLE_RE = re.compile(r"/wiki/([^/?#]+)")

__all__ = [
    "BaseExtractor",
    "ExtractedPage",
    "MediaWikiExtractor",
    "PlaywrightFallbackExtractor",
]


def _is_transient_network_error(exc: BaseException) -> bool:
    """Retry predicate covering aiohttp, timeouts and Playwright errors."""
    if isinstance(exc, (aiohttp.ClientError, OSError, asyncio.TimeoutError)):
        return True
    try:
        from playwright.async_api import Error as PlaywrightError

        return isinstance(exc, PlaywrightError)
    except ImportError:  # pragma: no cover - Playwright not installed
        return False


@dataclass(frozen=True)
class ExtractedPage:
    """Result of an extraction: clean text plus provenance metadata."""

    source_url: str
    page_title: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    """Abstract extraction strategy."""

    @abstractmethod
    async def extract(self, url: str) -> ExtractedPage:
        """Fetch ``url`` and return the page as clean, sectioned text.

        The returned ``ExtractedPage.text`` keeps the logical section
        structure: ``## Section`` / ``### Sub-section`` Markdown headings
        delimit the content blocks consumed by ``chunk_into_lorechunks``.
        """


def _title_from_url(url: str) -> str:
    """Extract the wiki page title from a Fandom URL (``.../wiki/Title``)."""
    match = URL_TITLE_RE.search(url)
    if not match:
        raise ValueError(f"URL invalide, aucun segment /wiki/: {url}")
    return match.group(1).replace("_", " ")


def _infobox_metadata(wikitext: str) -> Dict[str, Any]:
    """Extract ``key=value`` parameters of the first infobox template."""
    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates():
        if "infobox" not in str(template.name).strip().lower():
            continue
        properties: Dict[str, Any] = {}
        for param in template.params:
            name = param.name.strip_code(normalize=True, collapse=True).strip()
            value = param.value.strip_code(normalize=True, collapse=True).strip()
            if name and value:
                properties[name] = value
        if properties:
            return properties
    return {}


class MediaWikiExtractor(BaseExtractor):
    """Extract Wikitext through the Fandom MediaWiki API.

    Uses the ``prop=revisions`` endpooint with ``rvprop=content``, cleans
    the raw Wikitext via ``mwparserfromhell`` and keeps only the H2/H3
    section structure. An ``aiohttp.ClientSession`` may be injected to
    share connection pooling across the pipeline.
    """

    def __init__(
        self,
        api_endpoint: str = DEFAULT_API_ENDPOINT,
        session: Optional[aiohttp.ClientSession] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._api_endpoint = api_endpoint
        self._session = session
        self._user_agent = user_agent
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    @retry_network()
    async def extract(self, url: str) -> ExtractedPage:
        """Fetch the page revision via the API and clean the Wikitext."""
        page_title = _title_from_url(url)
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
            "titles": page_title,
        }
        headers = {"User-Agent": self._user_agent}
        session = self._session or aiohttp.ClientSession(
            headers=headers, timeout=self._timeout
        )
        try:
            async with session.get(self._api_endpoint, params=params) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        finally:
            if self._session is None:
                await session.close()

        pages = payload.get("query", {}).get("pages", [])
        if not pages or "missing" in pages[0]:
            raise LookupError(f"Page introuvable sur l'API: {page_title}")
        wikitext = pages[0]["revisions"][0]["slots"]["main"]["content"]

        logger.info("Fetched %d chars of Wikitext for '%s'", len(wikitext), page_title)
        return ExtractedPage(
            source_url=url,
            page_title=page_title,
            text=_wikitext_to_markdown(wikitext),
            metadata=_infobox_metadata(wikitext),
        )


class PlaywrightFallbackExtractor(BaseExtractor):
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

        try:
            from playwright.async_api import Error as PlaywrightError
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Playwright n'est pas installé: pip install playwright "
                "puis 'playwright install chromium'."
            ) from exc

    @retry_when(_is_transient_network_error)
    async def extract(self, url: str) -> ExtractedPage:
        """Load ``url`` headless, expand dynamic blocks and scrape the DOM."""
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until=self._wait_until, timeout=self._timeout_millis)
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


def _wikitext_to_markdown(wikitext: str) -> str:
    """Clean Wikitext into Markdown, keeping H2/H3 section headings.

    H2/H3 headings are replaced by private marker tokens before
    ``strip_code`` strips the markup, then restored as ``## Title`` /
    ``### Title``. Templates (infoboxes, navboxes) are dropped and links
    are reduced to their caption without fragmenting the surrounding text.
    """
    code = mwparserfromhell.parse(wikitext)
    markers: dict[str, str] = {}
    for index, heading in enumerate(code.filter_headings()):
        level = heading.level
        if level not in (2, 3):
            continue
        title = heading.title.strip_code(normalize=True, collapse=True).strip()
        if not title:
            continue
        marker = f"_WFC{index}_"
        code.replace(heading, marker)
        markers[marker] = f"\n{'#' * level} {title}\n"

    text = code.strip_code(normalize=False, collapse=True)
    for marker, markdown_heading in markers.items():
        text = text.replace(marker, markdown_heading)
    return text.strip()