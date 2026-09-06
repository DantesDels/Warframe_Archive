"""Source MediaWiki (wiki.warframe.com) — implémentation concrète de BaseSource.

Ce module encapsule TOUTE la communication avec l'API MediaWiki :
session HTTP, retries avec backoff exponentiel, throttling (politesse),
et pagination via le jeton ``continue``.

Conformément au principe SOLID *Single Responsibility*, ce module ne fait
QUE de la communication.  Aucun nettoyage de contenu n'a lieu ici.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterator

import requests

from .base import BaseSource
from .models import CategorySpec, PageData, TouchedInfo

log = logging.getLogger("warframe_lore.api.mediawiki")


class MediaWikiSourceError(RuntimeError):
    """Erreur non-transitoire de l'API MediaWiki."""


class RetryableHttp:
    """Mini-couche HTTP réutilisable : retries + backoff + throttling.

    Encapsulée séparément pour réutilisation par d'éventuels autres clients
    (principe DRY).  Gère aussi les erreurs API qui remontent en HTTP 200.
    """

    def __init__(self, api_url: str, user_agent: str, *, timeout: float = 60.0,
                 max_retries: int = 5, retry_backoff: float = 2.0,
                 min_sleep: float = 0.4, per_request_limit: int = 50) -> None:
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.min_sleep = min_sleep
        self.per_request_limit = per_request_limit
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.min_sleep - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def request(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET + retries + backoff, retourne le JSON parsé."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.get(self.api_url, params=params,
                                        timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                backoff = self.retry_backoff ** attempt
                log.warning("Requête échouée (%d/%d): %s; retente dans %.1fs",
                            attempt + 1, self.max_retries, exc, backoff)
                time.sleep(backoff)
                continue

            if "error" in data:
                code = data["error"].get("code", "unknown")
                if code in {"ratelimited", "maxlag"}:
                    time.sleep(self.retry_backoff)
                    continue
                raise MediaWikiSourceError(
                    f"Erreur API '{code}': {data['error'].get('info', '')}")
            return data

        raise MediaWikiSourceError(
            f"Requête échouée après {self.max_retries} tentatives: {last_exc}")

    def paged(self, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Itère sur les pages de résultats en suivant le jeton ``continue``."""
        p = dict(params)
        while True:
            data = self.request(p)
            yield data
            cont = data.get("continue", {})
            if not cont:
                break
            p.update({k: v for k, v in cont.items() if k != "continue"})


class MediaWikiSource(BaseSource):
    """Source de données officielle de Warframe (wiki.warframe.com)."""

    name = "mediawiki-warframe"

    def __init__(self, config) -> None:
        self.config = config
        self.http = RetryableHttp(
            api_url=config.api_url,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            min_sleep=config.min_sleep_between_requests,
            per_request_limit=config.per_request_limit,
        )

    # ------------------------------------------------------- BaseSource API
    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        """Récupère le contenu complet des pages demandées (par lot de 50)."""
        result: dict[str, PageData] = {}
        for i in range(0, len(titles), self.http.per_request_limit):
            chunk = titles[i:i + self.http.per_request_limit]
            for data in self.http.paged({
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "revisions|info",
                "rvprop": "content|timestamp", "rvslots": "main",
                "inprop": "touched|url",
                "titles": "|".join(chunk),
            }):
                for page in data.get("query", {}).get("pages", []):
                    if "pageid" not in page:
                        continue
                    revs = page.get("revisions") or []
                    content, ts = "", None
                    if revs:
                        slot = revs[0].get("slots", {}).get("main", {})
                        content = slot.get("content") or slot.get("*") or ""
                        ts = revs[0].get("timestamp")
                    pd = PageData(
                        pageid=page["pageid"],
                        title=page.get("title", ""),
                        namespace=page.get("ns", 0),
                        touched=page.get("touched"),
                        last_revision_timestamp=ts,
                        url=page.get("canonicalurl", ""),
                        content=content,
                    )
                    if pd.title:
                        result[pd.title] = pd
        return result

    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        """Métadonnées légères (touched) pour le calcul du delta."""
        result: dict[str, TouchedInfo] = {}
        for i in range(0, len(titles), self.http.per_request_limit):
            chunk = titles[i:i + self.http.per_request_limit]
            for data in self.http.paged({
                "action": "query", "format": "json", "formatversion": "2",
                "prop": "info", "inprop": "touched",
                "titles": "|".join(chunk),
            }):
                for page in data.get("query", {}).get("pages", []):
                    title = page.get("title", "")
                    if not title:
                        continue
                    result[title] = TouchedInfo(
                        pageid=page.get("pageid"),
                        title=title,
                        namespace=page.get("ns", 0),
                        touched=page.get("touched"),
                        missing=page.get("missing", False),
                    )
        return result

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
