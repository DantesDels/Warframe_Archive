"""Megafiles — incremental loading of ``out/*.json``.

Single responsibility: fingerprint the megafiles on disk (mtime/size),
reload only the changed ones, and rebuild the derived index views
(search docs, counts, sorted pages, titles, recents).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..dialogue import dialogue as dlg
from .search import _SearchDoc


class MegafilesMixin:
    """Rechargement incrémental + reconstruction des index dérivés.

    Seuls les megafiles dont l'empreinte (mtime, taille) a changé sont
    re-parsés ; les buckets inchangés sont conservés tels quels. Un verrou
    protège le reload contre les requêtes concurrentes du serveur threadé.
    """

    _RELOAD_INTERVAL = 5.0  # secondes entre deux relectures du disque

    def maybe_reload(self) -> None:
        """Recharge les megafiles au plus toutes les ``_RELOAD_INTERVAL`` s.

        Permet au front de voir de nouveaux megafiles (après ``cephalon run``)
        sans redémarrer le serveur.  Un scan d'empreintes (``stat``) évite de
        re-parser tout le corpus quand rien n'a changé.
        """
        if time.time() - self._last_reload < self._RELOAD_INTERVAL:
            return
        if self._scan_changed():
            self.reload()
        else:
            self._last_reload = time.time()

    def _fingerprints(self) -> dict[str, tuple[int, int]]:
        """Empreinte (mtime_ns, taille) de chaque megafile, par nom."""
        state: dict[str, tuple[int, int]] = {}
        if self.output_dir.is_dir():
            for megafile in self.output_dir.glob("*.json"):
                try:
                    st = megafile.stat()
                except OSError:
                    continue
                state[megafile.name] = (st.st_mtime_ns, st.st_size)
        return state

    def _scan_changed(self) -> bool:
        with self._lock:
            return self._fingerprints() != self._file_state

    def reload(self) -> None:
        """(Re)charge les megafiles ``out/*.json`` modifiés depuis le disque.

        Les buckets inchangés sont conservés tels quels ; les index dérivés ne
        sont reconstruits que si au moins un fichier a réellement changé.
        """
        with self._lock:
            fingerprints = self._fingerprints()
            if fingerprints == self._file_state and self._recent:
                self._last_reload = time.time()
                return

            buckets = dict(self._buckets)
            pages = dict(self._pages)
            for name in set(self._file_state) - set(fingerprints):
                bucket_id = Path(name).stem
                buckets.pop(bucket_id, None)
                pages.pop(bucket_id, None)
            for name in sorted(fingerprints):
                if self._file_state.get(name) == fingerprints[name]:
                    continue
                self._parse_megafile(
                    self.output_dir / name, Path(name).stem, buckets, pages)

            self._file_state = fingerprints
            self._buckets = buckets
            self._pages = pages
            self._rebuild_indexes()
            self.kim_dm.load()
            self._last_reload = time.time()

    def _parse_megafile(self, path: Path, bucket_id: str,
                        buckets: dict, pages: dict) -> None:
        """Parse un megafile et remplace l'entrée de son bucket."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        metadata = data.get("metadata") or {}
        entries = data.get("pages") or []
        buckets[bucket_id] = {
            "id": bucket_id,
            "title": self._bucket_title(bucket_id, metadata),
            "filename": path.name,
            "generated_at": metadata.get("generated_at"),
            "total_pages": len(entries),
        }
        pages[bucket_id] = {e["page_title"]: e for e in entries
                            if e.get("page_title")}

    @staticmethod
    def _bucket_title(bucket_id: str, metadata: dict) -> str:
        title = metadata.get("bucket_title", bucket_id)
        for suffix in (" (voix)", " (transcripts)"):
            if title.endswith(suffix):
                title = title[: -len(suffix)]
        if bucket_id == dlg.KIM_BUCKET_ID:
            title = "Terminal KIM"
        return title

    def _rebuild_indexes(self) -> None:
        """Recalcule les vues dérivées (recherche, compteurs, récents)."""
        docs: list[_SearchDoc] = []
        counts: dict[str, dict[str, int]] = {}
        pages_sorted: dict[str, list[dict]] = {}
        titles_by_bucket: dict[str, list[str]] = {}
        recent: list[dict] = []
        for bucket_id, entries in self._pages.items():
            canon = speculation = 0
            light: list[dict] = []
            titles: list[str] = []
            for e in entries.values():
                title = e["page_title"]
                content = e.get("content_markdown", "")
                docs.append(_SearchDoc(bucket_id, e, title.casefold(),
                                       content.casefold()))
                status = e.get("canon_status")
                if status == "canon":
                    canon += 1
                elif status == "speculation":
                    speculation += 1
                titles.append(title)
                light.append({
                    "page_title": title,
                    "canon_status": status,
                    "last_updated": e.get("last_updated"),
                })
                recent.append({
                    "bucket_id": bucket_id,
                    "page_title": title,
                    "canon_status": status,
                    "last_updated": e.get("last_updated"),
                })
            light.sort(key=lambda x: x["page_title"].lower())
            titles.sort(key=str.lower)
            counts[bucket_id] = {"canon": canon, "speculation": speculation}
            pages_sorted[bucket_id] = light
            titles_by_bucket[bucket_id] = titles
        recent.sort(key=lambda r: r["last_updated"] or "", reverse=True)
        self._search_docs = docs
        self._bucket_counts = counts
        self._pages_sorted = pages_sorted
        self._titles_by_bucket = titles_by_bucket
        self._recent = recent
