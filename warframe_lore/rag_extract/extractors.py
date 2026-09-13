"""Extraction strategies for the decoupled RAG pipeline.

``BaseExtractor`` defines the strategy contract; ``MediaWikiExtractor`` is
the primary strategy (Wikitext via the Fandom MediaWiki API).  The DOM
fallback for client-rendered pages lives in
:mod:`warframe_lore.rag_extract.dom_scraper`
(``PlaywrightFallbackExtractor``).

Every network call is wrapped with a Tenacity retry policy (3 attempts,
exponential backoff) defined in the ``resilience`` helpers.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import aiohttp
import mwparserfromhell

from .resilience import retry_network

logger = logging.getLogger(__name__)

DEFAULT_API_ENDPOINT = "https://warframe.fandom.com/api.php"
DEFAULT_USER_AGENT = "WarframeArchives-RAGPipeline/1.0 (aiohttp + mwparserfromhell)"
URL_TITLE_RE = re.compile(r"/wiki/([^/?#]+)")

__all__ = [
    "BaseExtractor",
    "ExtractedPage",
    "MediaWikiExtractor",
]


@dataclass(frozen=True)
class ExtractedPage:
    """Result of an extraction: clean text plus provenance metadata."""

    source_url: str
    page_title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


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


def _infobox_metadata(wikitext: str) -> dict[str, Any]:
    """Extract ``key=value`` parameters of the first infobox template."""
    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates():
        if "infobox" not in str(template.name).strip().lower():
            continue
        properties: dict[str, Any] = {}
        for param in template.params:
            name = param.name.strip_code(normalize=True, collapse=True).strip()
            value = param.value.strip_code(normalize=True, collapse=True).strip()
            if name and value:
                properties[name] = value
        if properties:
            return properties
    return {}


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
        session: aiohttp.ClientSession | None = None,
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
