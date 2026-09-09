"""Wiki category and prefix resolution (MediaWikiSource mixin).

HTTP cataloguing logic for the Vitripedia page families: recursive
expansion of the subcategories and prefix-based discovery via
``list=allpages``.
"""

from __future__ import annotations


class MediaWikiCategoryMixin:
    """Category / prefix resolution (depends on ``self.http``)."""

    def resolve_categories(
        self,
        category_names: list[str],
    ) -> dict[str, set[str]]:
        """Expands wiki categories into page titles (including subcategories)."""
        out: dict[str, set[str]] = {}
        for name in category_names:
            out[name] = self._category_members_recursive(name)
        return out

    def resolve_prefix(self, prefix: str) -> set[str]:
        """All titles (ns=0) starting with ``prefix``.

        Complementary to categories: some page families (e.g.
        ``Kinemantik Instant Messenger/Flare``) are not listed in a
        category resolved by :meth:`resolve_categories`.  They are then
        discovered via ``list=allpages&apprefix=``, discarding structural
        pages (empty roots ``title/``, files ``/File:``).
        """
        pages: set[str] = set()
        for data in self.http.paged({
            "action": "query", "format": "json", "formatversion": "2",
            "list": "allpages", "apprefix": prefix,
            "apnamespace": "0", "aplimit": str(self.http.per_request_limit),
        }):
            for p in data.get("query", {}).get("allpages", []):
                title = p.get("title", "")
                if not title:
                    continue
                if title == prefix or title.endswith("/"):
                    continue
                if "/File:" in title:
                    continue
                pages.add(title)
        return pages

    # ------------------------------------------------- internal helpers
    def _category_members(self, category: str) -> list[tuple[int, str]]:
        """All members ``(namespace, title)`` of a category."""
        cleantitle = (category if category.lower().startswith("category:")
                      else "Category:" + category)
        members: list[tuple[int, str]] = []
        for data in self.http.paged({
            "action": "query", "format": "json", "formatversion": "2",
            "list": "categorymembers", "cmtitle": cleantitle,
            "cmlimit": str(self.http.per_request_limit),
        }):
            for m in data.get("query", {}).get("categorymembers", []):
                members.append((m.get("ns", 0), m.get("title", "")))
        return members

    def _category_members_recursive(self, category: str,
                                    _depth: int = 0) -> set[str]:
        """Returns the pages (ns=0) of a category by walking through the
        subcategories."""
        if _depth > self.config.max_category_depth:
            return set()
        pages: set[str] = set()
        for ns, title in self._category_members(category):
            if ns == 14:  # sub-category
                if self.config.follow_subcategories:
                    pages |= self._category_members_recursive(
                        title.removeprefix("Category:"), _depth + 1)
            elif ns == 0:
                pages.add(title)
        return pages