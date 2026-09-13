"""LoreStore — cache en mémoire des megafiles ``out/*.json``.

Responsabilité unique : charger les megafiles, exposer pages/buckets,
recherche, recents, statistiques et projections de dialogue KIM.  Le parsing
fin des répliques/scripts/graphes vit dans ``dialogue*`` ; ici seuls les
accès cohérents au corpus.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, NamedTuple

from ..kim_dm import KimDM
from . import dialogue as dlg
from .dialogue_graph import build_dialogue_graph
from .dialogue_script import build_kim_script


class _SearchDoc(NamedTuple):
    """Vue précalculée d'une page pour la recherche (casefold fait 1 fois)."""

    bucket_id: str
    entry: dict
    title_fold: str
    content_fold: str


class LoreStore:
    """Cache en mémoire des megafiles ``out/*.json`` + recherche.

    Le rechargement est **incrémental** : seuls les megafiles dont l'empreinte
    (mtime, taille) a changé sont re-parsés, et les index dérivés (recherche,
    compteurs, récents) ne sont reconstruits qu'à cette occasion. Un verrou
    protège le reload contre les requêtes concurrentes du serveur threadé.
    """

    _RELOAD_INTERVAL = 5.0  # secondes entre deux relectures du disque

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.kim_dm = KimDM(
            self.output_dir / "kim_dm" / "data",
            self.output_dir / "kim_dm" / "dicts",
        )
        self._lock = threading.RLock()
        self._file_state: dict[str, tuple[int, int]] = {}
        self._buckets: dict[str, dict[str, Any]] = {}
        self._pages: dict[str, dict[str, dict]] = {}
        self._search_docs: list[_SearchDoc] = []
        self._bucket_counts: dict[str, dict[str, int]] = {}
        self._pages_sorted: dict[str, list[dict]] = {}
        self._titles_by_bucket: dict[str, list[str]] = {}
        self._recent: list[dict] = []
        self._last_reload = 0.0
        self.reload()

    # ------------------------------------------------------------- reloading
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

    # ---------------------------------------------------------------- média
    def page_titles_by_bucket(self) -> dict[str, list[str]]:
        """Titres de toutes les pages de l'archive, groupés par bucket."""
        return self._titles_by_bucket

    def kim_speakers(self) -> list[str]:
        """Locuteurs rencontrés dans le Terminal KIM (ordre d'apparition)."""
        seen: list[str] = []
        for entry in self._pages.get(dlg.KIM_BUCKET_ID, {}).values():
            for speaker in dlg.speakers(entry.get("content_markdown", "")):
                if speaker not in seen:
                    seen.append(speaker)
        return seen

    # -------------------------------------------------------------- buckets
    def list_buckets(self) -> list[dict]:
        return [
            {
                "id": b["id"],
                "title": b["title"],
                "generated_at": b["generated_at"],
                "total_pages": b["total_pages"],
                "canon": self._count_canon(b["id"]),
                "speculation": self._count_status(b["id"], "speculation"),
            }
            for b in sorted(self._buckets.values(), key=lambda x: x["title"].lower())
        ]

    def _count_canon(self, bucket_id: str) -> int:
        return self._bucket_counts.get(bucket_id, {}).get("canon", 0)

    def _count_status(self, bucket_id: str, status: str) -> int:
        return self._bucket_counts.get(bucket_id, {}).get(status, 0)

    def bucket_exists(self, bucket_id: str) -> bool:
        return bucket_id in self._pages

    def list_pages(self, bucket_id: str) -> list[dict]:
        """Liste légère (sans le contenu) des pages d'un bucket, triée."""
        return self._pages_sorted.get(bucket_id, [])

    def get_page(self, bucket_id: str, title: str) -> dict | None:
        return self._pages.get(bucket_id, {}).get(title)

    # ------------------------------------------------------------- dialogues
    def kim_pages(self) -> list[dict]:
        """Pages du Terminal KIM : strictement le bucket ``Lore_Dialogues_KIM``.

        (Bucket source de vérité — 16 pages — à l'exclusion des dialogues
        « ressemblants » dispersés dans les autres buckets : armes, quêtes…)
        """
        out: list[dict] = []
        for e in self._pages.get(dlg.KIM_BUCKET_ID, {}).values():
            content = e.get("content_markdown", "")
            out.append({
                "bucket_id": dlg.KIM_BUCKET_ID,
                "page_title": e["page_title"],
                "canon_status": e.get("canon_status"),
                "line_count": content.count("\n") + 1,
                "conversations": len(self.kim_conversations(e["page_title"])),
                "speakers": dlg.speakers(content),
            })
        return sorted(out, key=lambda x: x["page_title"].lower())

    def kim_conversations(self, title: str) -> list[dict]:
        """Conversations d'une page KIM : ``[{id, title, rank, body}]``.

        Priorité au miroir de datamine (données du jeu) quand le personnage y
        est couvert (ids ``ArthurRank1Convo1``…).  Sinon, découpage par
        sections wiki (fallback historique).
        """
        page = self.get_dialogue_page(title)
        if not page:
            return []
        content = page.get("content_markdown", "")
        character = title.rsplit("/", 1)[-1].strip()
        dm = self.kim_dm.conversations_for(character)
        if dm is not None:
            return dm
        conversations = dlg.split_kim_conversations(title, content)
        if conversations:
            return conversations
        if dlg.looks_like_dialogue(content):
            return [{
                "id": f"{dlg.slug_for_id(character)}Conversation",
                "title": character or title,
                "rank": "",
                "body": content,
            }]
        return []

    def kim_dialogue(self, title: str) -> list[dict] | None:
        """Dialogue structuré : liste de ``{speaker, text}``."""
        for e in self._all_pages():
            if e["page_title"] == title and dlg.looks_like_dialogue(
                    e.get("content_markdown", "")):
                return dlg.parse_dialogue(e["content_markdown"])
        return None

    def get_dialogue_page(self, title: str) -> dict | None:
        """Page brute (markdown) correspondant au dialogue, si elle existe."""
        for e in self._all_pages():
            if e["page_title"] == title:
                return e
        return None

    def kim_graph(self, title: str, conv: str | None = None) -> dict | None:
        """Graphe de conversation (``{nodes, edges}``) d'une page de dialogue.

        Utilisé par la vue flowchart.  Si ``conv`` est fourni, seuls les
        nœuds/arêtes de cette conversation sont renvoyés ; sinon le graphe de
        la page entière.  Retourne ``None`` si introuvable / pas un dialogue.
        """
        character = title.rsplit("/", 1)[-1].strip()
        dm_graph = self.kim_dm.graph(character, conv)
        if dm_graph is not None:
            return dm_graph
        page = self.get_dialogue_page(title)
        if not page:
            return None
        content = page.get("content_markdown", "")
        if not dlg.looks_like_dialogue(content):
            return None
        if conv:
            for conversation in dlg.split_kim_conversations(title, content):
                if conversation["id"] == conv:
                    return build_dialogue_graph(
                        conversation["body"],
                        root_label=f"{conversation['id']} begins")
            return None
        return build_dialogue_graph(
            content, root_label=f"{character} · toutes les conversations")

    # ----------------------------------------------------- projection légère
    def _all_pages(self):
        for entries in self._pages.values():
            yield from entries.values()

    @staticmethod
    def _looks_like_dialogue(content: str) -> bool:
        return dlg.looks_like_dialogue(content)

    @staticmethod
    def _clean_kim_text(text: str) -> str:
        return dlg.clean_kim_text(text)

    @staticmethod
    def _speakers(content: str) -> list[str]:
        return dlg.speakers(content)

    @staticmethod
    def _is_player_speaker(speaker: str) -> bool:
        return dlg.is_player_speaker(speaker)

    @classmethod
    def _parse_dialogue(cls, content: str) -> list[dict]:
        return dlg.parse_dialogue(content)

    @staticmethod
    def spoiler_warning(content: str) -> str | None:
        return dlg.spoiler_warning(content)

    @staticmethod
    def _norm_dialogue_ref(text: str) -> str:
        return dlg.normalise_dialogue_ref(text)

    @classmethod
    def _build_kim_script(cls, content: str) -> list[dict]:
        return build_kim_script(content)

    # ---------------------------------------------------------------- recent
    def recent(self, limit: int = 20) -> list[dict]:
        """Pages triées par ``last_updated`` décroissant (index précalculé)."""
        return self._recent[:limit]

    # ---------------------------------------------------------------- search
    def search(self, query: str, limit: int = 50, *,
               bucket: str | None = None, canon: str | None = None) -> list[dict]:
        """Recherche plein texte avec pondération stricte des titres.

        Hiérarchie absolue : toute page dont le *titre* contient la requête
        (insensible à la casse, partielle) est rendue en tête de liste, avant
        les simples mentions du terme dans le contenu.  Chaque résultat
        expose ``match_type`` (``title``/``content``).
        """
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for doc in self._search_docs:
            if bucket and doc.bucket_id != bucket:
                continue
            if canon and doc.entry.get("canon_status") != canon:
                continue
            content = doc.entry.get("content_markdown", "")
            if needle in doc.title_fold:
                title_hits.append(self._ranked_hit(
                    doc.entry, doc.bucket_id, query, content, "title"))
            elif needle in doc.content_fold:
                content_hits.append(self._ranked_hit(
                    doc.entry, doc.bucket_id, query, content, "content"))
        title_hits.sort(key=lambda r: (r["bucket_id"],
                                       r["page_title"].casefold()))
        content_hits.sort(key=lambda r: (r["bucket_id"],
                                         r["page_title"].casefold()))
        return (title_hits + content_hits)[:limit]

    @staticmethod
    def _ranked_hit(e: dict, bucket_id: str, query: str,
                    content: str, match_type: str) -> dict:
        """Construit un résultat de recherche pondéré (titre vs contenu)."""
        return {
            "bucket_id": bucket_id,
            "page_title": e["page_title"],
            "canon_status": e.get("canon_status"),
            "last_updated": e.get("last_updated"),
            "match_type": match_type,
            "snippet": dlg.make_snippet(content, query),
        }

    def suggest(self, query: str, limit: int = 8) -> list[dict]:
        """Autocomplétion : titres contenant ``query`` (+ contexte bucket)."""
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for doc in self._search_docs:
            bucket_id = doc.bucket_id
            bucket_title = self._buckets.get(bucket_id, {}).get("title",
                                                                bucket_id)
            e = doc.entry
            title = e["page_title"]
            title_hit = needle in doc.title_fold
            content_hit = needle in doc.content_fold
            if title_hit:
                title_hits.append({
                    "page_title": title,
                    "bucket_id": bucket_id,
                    "bucket_title": bucket_title,
                    "canon_status": e.get("canon_status"),
                    "match_type": "title",
                    "snippet": "",
                })
            elif content_hit:
                content_hits.append({
                    "page_title": title,
                    "bucket_id": bucket_id,
                    "bucket_title": bucket_title,
                    "canon_status": e.get("canon_status"),
                    "match_type": "content",
                    "snippet": dlg.make_snippet(
                        e.get("content_markdown", ""), query, radius=44),
                })
        title_hits.sort(key=lambda r: (r["bucket_id"],
                                       r["page_title"].casefold()))
        content_hits.sort(key=lambda r: (r["bucket_id"],
                                         r["page_title"].casefold()))
        return (title_hits + content_hits)[:limit]

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict[str, Any]:
        total_pages = sum(len(e) for e in self._pages.values())
        canon = sum(self._count_canon(b) for b in self._pages)
        speculation = sum(self._count_status(b, "speculation")
                          for b in self._pages)
        return {
            "buckets": len(self._buckets),
            "pages": total_pages,
            "canon": canon,
            "speculation": speculation,
            "kim_dialogues": len(self.kim_pages()),
            "last_update": max(
                (b["generated_at"] for b in self._buckets.values()
                 if b["generated_at"]),
                default=None,
            ),
        }
