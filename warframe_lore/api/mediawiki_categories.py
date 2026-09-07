"""Résolution des catégories et préfixes wiki (mixin de MediaWikiSource).

La logique de catalogage HTTP des familles de pages Vitripedia : expansion
récursive des sous-catégories et découverte par ``list=allpages`` (préfixes).
"""

from __future__ import annotations


class MediaWikiCategoryMixin:
    """Résolution de catégories / préfixes (dépend de ``self.http``)."""

    def resolve_categories(
        self,
        category_names: list[str],
    ) -> dict[str, set[str]]:
        """Développe des catégories wiki en titres de pages (avec sous-catégories)."""
        out: dict[str, set[str]] = {}
        for name in category_names:
            out[name] = self._category_members_recursive(name)
        return out

    def resolve_prefix(self, prefix: str) -> set[str]:
        """Tous les titres (ns=0) commençant par ``prefix``.

        Complémentaire aux catégories : certaines familles de pages (ex:
        ``Kinemantik Instant Messenger/Flare``) ne sont pas listées dans une
        catégorie résolue par :meth:`resolve_categories`.  On les découvre
        alors via ``list=allpages&apprefix=``, en écartant les pages
        structurelles (racines vides ``titre/``, fichiers ``/File:``).
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
        """Tous les membres ``(namespace, titre)`` d'une catégorie."""
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
        """Retourne les pages (ns=0) d'une catégorie en parcourant les
        sous-catégories."""
        if _depth > self.config.max_category_depth:
            return set()
        pages: set[str] = set()
        for ns, title in self._category_members(category):
            if ns == 14:  # sous-catégorie
                if self.config.follow_subcategories:
                    pages |= self._category_members_recursive(
                        title.removeprefix("Category:"), _depth + 1)
            elif ns == 0:
                pages.add(title)
        return pages