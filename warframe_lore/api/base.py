"""Abstract interface for all data sources.

The project is designed to be extensible: today we only consume the
MediaWiki wiki (``MediaWikiSource``), but tomorrow it will be possible to
plug in Reddit, the official Forums, etc.  This interface is what makes
that evolution possible without touching the rest of the pipeline
(scraper, cleaner, output).

Each new source must:
  * inherit from :class:`BaseSource` ;
  * implement the three abstract methods (fetch_pages, check_updates,
    resolve_categories) ;
  * remain a PURE communication component (no cleaning here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import CategorySpec, PageData, TouchedInfo

__all__ = ["BaseSource", "CategorySpec", "PageData", "TouchedInfo"]


class BaseSource(ABC):
    """Common interface to all data sources.

    The pipeline (``scraper.py``) depends only on this interface.  This
    respects the SOLID *Dependency Inversion* principle: high-level code
    does not depend on concrete implementations.
    """

    name: str = "base"

    @abstractmethod
    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        """Fetches the full content of the requested pages.

        Returns:
            Mapping ``title -> PageData`` (only the pages found).
        """

    @abstractmethod
    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        """Fetches only the modification metadata (``touched`` field).

        Used for delta mode: it is compared against the local state to
        decide which pages to re-download.
        """

    @abstractmethod
    def resolve_categories(
        self,
        category_names: list[str],
    ) -> dict[str, set[str]]:
        """Resolves categories into lists of page titles.

        Args:
            category_names: names of the categories to expand.

        Returns:
            Mapping ``category_name -> set of page titles`` (subcategories
            included depending on the source).
        """

    def resolve_prefix(self, prefix: str) -> set[str]:
        """Titles (ns=0) starting with ``prefix`` (prefix-based discovery).

        Non-abstract method: sources that do not support prefix-based
        discovery simply return an empty set.  Those that support it (e.g.
        MediaWiki ``list=allpages``) override it.
        """
        return set()