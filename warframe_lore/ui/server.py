"""Interface ``cephalon ui`` : mini serveur HTTP + compacteur JSON Gzip.

Sert l'interface web (frontend statique intégré au paquet) et expose une API
JSON REST pour parcourir le lore récupéré depuis les megafiles ``out/``.

Endpoints :
    * ``GET /``                     -> index.html (interface)
    * ``GET /api/buckets``          -> buckets + comptages
    * ``GET /api/pages?bucket=ID``  -> pages d'un bucket
    * ``GET /api/page?bucket=ID&title=T`` -> contenu d'une page (Markdown)
    * ``GET /api/kim``              -> dialogue(s) KIM
    * ``GET /api/recent``           -> pages récentes
    * ``GET /api/search?q=...``     -> recherche plein texte
    * ``GET /api/stats``            -> indicateurs globaux

Aucune dépendance externe (stdlib uniquement : ``http.server``, ``json``,
``gzip``).  La sortie est gzip-serve pour les gros documents KIM.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

from ..kim_dm import KimDM, _anchor_graph
from ..media import MediaIndex

# --------------------------------------------------------------------------
# Lecteur de megafiles (couche "données" : out/*.json).
# --------------------------------------------------------------------------
_BLOCKQUOTE_SPEAKER = re.compile(r"^>\s*\*\*(?P<speaker>[^*:]+):\*\*\s*(?P<text>.*)$")

KIM_BUCKET_ID = "Lore_Dialogues_KIM"

# Boilerplate d'en-tête des pages KIM (à exclure des dialogues).
_BOILERPLATE_LINE = re.compile(
    r"^>?\s*(\*_SPOILERS_\*|_?:|_ |Notes:|All ending conversations|"
    r"A flow chart will be included|"
    r"The corresponding flow chart|Any glowing, golden text|"
    r"Indented messages|All user input is marked|All user's choices|"
    r"Rank [0-9]|Alty|_SPOILERS_|"
    r"[\(\{\[\[]?\s*(line|lines)\s+(required|needed|reqquired)|"
    r"[\(\{\[\[]?\s*(same as (the )?below|same\s*-?\s*as\s+-?\s*above|"
    r"goes the same as below choice|jump to above branch|"
    r"jump to \"|choices same as|"
    r"to next set of choices|end of conversation|continues as above|"
    r"continues above)|"
    r"^>?\s*[^A-Za-z0-9]{0,3}\s*DFF\w+\.ogg|-\s*[A-Z]?\.?\s*Lyon\b)", re.I)

# Avertissement spoiler : ``> *_SPOILERS_* _: <raison>_``
_SPOILER_WARNING = re.compile(
    r"^>?\s*\*_SPOILERS_\*\s*_?:\s*(?P<reason>.+?)_?\s*$", re.I)

# Instruction de navigation KIM en tête de ligne de dialogue (pointeurs wiki) :
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# et les variantes préfixées par une ou plusieurs conditions
# ``> **{If ...} {If ...} {Continues ...}`` ou ``> **> {...`` / ``> > {...``.
# Le mot-clé de navigation vit TOUJOURS dans une accolade : jamais dans le
# texte d'une réplique ordinaire.  La fermeture de l'accolade n'est pas exigée
# (le wiki ne la pose pas toujours).  ``{If ...} Name:`` et ``{Convo. ends.}``
# ne contiennent pas ces mots-clés -> non concernés.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
# Pointeur de navigation embarqué au milieu d'un message (fermé) : ``{...}``
# contenant un mot-clé de navigation -> retiré du texte du message.  Exige la
# fermeture de l'accolade pour ne jamais tronquer la réplique, et exclut les
# marqueurs terminaux ``{... ends ...}`` (ex: ``{Convo. Ends. Followed by
# jumpscare image.}``) qui pourraient contenir ``jump`` ou ``same``.
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
# Conditions de branche (``{If ...}``) et marqueurs de position (``{P1}``…) :
# purgés du texte des messages (locuteur/parole) mais pas de ``{Convo. ends.}``,
# des didascalies (``{Smile!}``) ni des autres accolades.
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)

# Titres de section qui délimitent une conversation KIM (``###``/``####`` …) :
#   ``### Conversation 1 (Tell me about yourself / ...)``
_KIM_SECTION_TITLE = re.compile(r"^#{3,}\s*(?P<title>.+?)\s*$")
# En-tête de rang qui précède les conversations : ``## Rank 1 - Neutral``
# (souvent ``= Rank 1 - =`` côté wiki -> rendu ``##`` par le cleaner).
_KIM_RANK_TITLE = re.compile(
    r"^#{1,3}\s+Rank\s+(?P<n>\d+)\s*[-–—:]\s*(?P<label>.+)$", re.I)
# Numéro d'une conversation dans son titre : ``Conversation 3 (...)``.
_KIM_CONVO_NUMBER = re.compile(r"^Conversation\s+(\d+)\b", re.I)


class LoreStore:
    """Cache en mémoire des megafiles ``out/*.json`` + recherche."""

    _RELOAD_INTERVAL = 5.0  # secondes entre deux relectures du disque

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.kim_dm = KimDM(
            self.output_dir / "kim_dm" / "data",
            self.output_dir / "kim_dm" / "dicts",
        )
        self._buckets: dict[str, dict[str, Any]] = {}
        self._pages: dict[str, dict[str, dict]] = {}
        self._last_reload = 0.0
        self.reload()

    def maybe_reload(self) -> None:
        """Recharge les megafiles au plus toutes les ``_RELOAD_INTERVAL`` s.

        Permet au front de voir de nouveaux megafiles (après ``cephalon run``)
        sans redémarrer le serveur."
        """
        if time.time() - self._last_reload >= self._RELOAD_INTERVAL:
            self.reload()

    def reload(self) -> None:
        """(Re)charge tous les megafiles ``out/*.json`` depuis le disque."""
        buckets: dict[str, dict[str, Any]] = {}
        pages: dict[str, dict[str, dict]] = {}
        if self.output_dir.is_dir():
            for megafile in sorted(self.output_dir.glob("*.json")):
                try:
                    data = json.loads(megafile.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                metadata = data.get("metadata") or {}
                bucket_id = megafile.stem
                entries = data.get("pages") or []
                title = metadata.get("bucket_title", bucket_id)
                for suffix in (" (voix)", " (transcripts)"):
                    if title.endswith(suffix):
                        title = title[: -len(suffix)]
                if bucket_id == KIM_BUCKET_ID:
                    title = "Terminal KIM"
                buckets[bucket_id] = {
                    "id": bucket_id,
                    "title": title,
                    "filename": megafile.name,
                    "generated_at": metadata.get("generated_at"),
                    "total_pages": len(entries),
                }
                pages[bucket_id] = {e["page_title"]: e for e in entries
                                    if e.get("page_title")}
        self._buckets = buckets
        self._pages = pages
        self.kim_dm.load()
        self._last_reload = time.time()

    # ---------------------------------------------------------------- média
    def page_titles_by_bucket(self) -> dict[str, list[str]]:
        """Titres de toutes les pages de l'archive, groupés par bucket."""
        return {
            bucket_id: [e["page_title"] for e in entries.values()]
            for bucket_id, entries in self._pages.items()
        }

    def kim_speakers(self) -> list[str]:
        """Locuteurs rencontrés dans le Terminal KIM (ordre d'apparition)."""
        seen: list[str] = []
        for entry in self._pages.get(KIM_BUCKET_ID, {}).values():
            for speaker in self._speakers(entry.get("content_markdown", "")):
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
        return self._count_status(bucket_id, "canon")

    def _count_status(self, bucket_id: str, status: str) -> int:
        return sum(1 for e in self._pages.get(bucket_id, {}).values()
                   if e.get("canon_status") == status)

    def bucket_exists(self, bucket_id: str) -> bool:
        return bucket_id in self._pages

    def list_pages(self, bucket_id: str) -> list[dict]:
        """Liste légère (sans le contenu) des pages d'un bucket."""
        return [
            {
                "page_title": e["page_title"],
                "canon_status": e.get("canon_status"),
                "last_updated": e.get("last_updated"),
            }
            for e in sorted(self._pages.get(bucket_id, {}).values(),
                            key=lambda x: x["page_title"].lower())
        ]

    def get_page(self, bucket_id: str, title: str) -> dict | None:
        return self._pages.get(bucket_id, {}).get(title)

    # ------------------------------------------------------------- dialogues
    def kim_pages(self) -> list[dict]:
        """Pages du Terminal KIM : strictement le bucket ``Lore_Dialogues_KIM``.

        (Bucket source de vérité — 16 pages — à l'exclusion des dialogues
        « ressemblants » dispersés dans les autres buckets : armes, quêtes, etc.)"""
        out: list[dict] = []
        for e in self._pages.get(KIM_BUCKET_ID, {}).values():
            content = e.get("content_markdown", "")
            out.append({
                "bucket_id": KIM_BUCKET_ID,
                "page_title": e["page_title"],
                "canon_status": e.get("canon_status"),
                "line_count": content.count("\n") + 1,
                "conversations": len(self.kim_conversations(e["page_title"])),
                "speakers": self._speakers(content),
            })
        return sorted(out, key=lambda x: x["page_title"].lower())

    def kim_conversations(self, title: str) -> list[dict]:
        """Conversations d'une page KIM : ``[{id, title, rank, body}]``.

        Priorité au miroir de datamine (données du jeu, section 1) quand le
        personnage y est couvert : les conversations sont alors exactes
        (ids ``ArthurRank1Convo1``, ``ArthurAmirHack``…) et ``body`` est
        absente (les messages/script/graphe viennent de ``kim_dm``).
        Sinon, découpage par sections wiki (fallback historique).
        Retourne ``[]`` si la page n'existe pas ou ne ressemble pas à un
        dialogue.
        """
        page = self.get_dialogue_page(title)
        if not page:
            return []
        content = page.get("content_markdown", "")
        character = title.rsplit("/", 1)[-1].strip()
        dm = self.kim_dm.conversations_for(character)
        if dm is not None:
            return dm
        conversations = _split_kim_conversations(title, content)
        if conversations:
            return conversations
        if self._looks_like_dialogue(content):
            return [{
                "id": f"{_slug_for_id(character)}Conversation",
                "title": character or title,
                "rank": "",
                "body": content,
            }]
        return []

    def kim_dialogue(self, title: str) -> list[dict] | None:
        """Dialogue structuré : liste de ``{speaker, text}``."""
        for e in self._all_pages():
            if e["page_title"] == title and self._looks_like_dialogue(
                    e.get("content_markdown", "")):
                return self._parse_dialogue(e["content_markdown"])
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
        nœuds/arêtes de cette conversation (découpée par ``_split_kim_conversations``)
        sont renvoyés ; sinon le graphe de la page entière (comportement
        historique).  Retourne ``None`` si la page n'existe pas, ne ressemble
        pas à un dialogue, ou si ``conv`` est introuvable.
        """
        character = title.rsplit("/", 1)[-1].strip()
        dm_graph = self.kim_dm.graph(character, conv)
        if dm_graph is not None:
            return dm_graph
        page = self.get_dialogue_page(title)
        if not page:
            return None
        content = page.get("content_markdown", "")
        if not self._looks_like_dialogue(content):
            return None
        if conv:
            for conversation in _split_kim_conversations(title, content):
                if conversation["id"] == conv:
                    return _build_dialogue_graph(
                        conversation["body"],
                        root_label=f"{conversation['id']} begins")
            return None
        return _build_dialogue_graph(
            content, root_label=f"{character} · toutes les conversations")

    def _all_pages(self):
        for entries in self._pages.values():
            yield from entries.values()

    @staticmethod
    def _looks_like_dialogue(content: str) -> bool:
        return any(line.strip().startswith("> **")
                   for line in content.splitlines()[:200])

    @staticmethod
    def _clean_kim_text(text: str) -> str:
        """Retire les instructions d'enchaînement KIM d'un texte.

        Purge les conditions de branche (``{If ...}``), marqueurs de position
        (``{P1}`` … ``{P5}``) et pointeurs de navigation fermés (``{Continues
        ...}``, ``{Same ...}``, ``{Jump ...}``, ``{Goes ...}``) embarqués dans
        le message.  Les didascalies (``{Smile!}``, …) et ``{Convo. ends.}``
        (terminal) sont conservées.
        """
        cleaned = _KIM_INLINE_NAV.sub("", text or "")
        cleaned = _KIM_CONDITION_MARK.sub("", cleaned)
        cleaned = _KIM_POSITION_MARK.sub("", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _speakers(content: str) -> list[str]:
        speakers: list[str] = []
        for line in content.splitlines():
            if _KIM_POINTER_LINE.match(line):
                continue
            match = _BLOCKQUOTE_SPEAKER.match(line.strip())
            if match:
                name = match.group("speaker").strip()
                name = LoreStore._clean_kim_text(name)
                if name and name not in speakers:
                    speakers.append(name)
        return speakers

    @staticmethod
    def _is_player_speaker(speaker: str) -> bool:
        """Vrai si le locuteur est le personnage du joueur (Tenno)."""
        return bool(re.search(
            r"operator|player|\btenno\b|drifter|walley|indifference", speaker, re.I))

    @staticmethod
    def _parse_dialogue(content: str) -> list[dict]:
        messages: list[dict] = []
        for index, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            # Lignes "boilerplate" des pages KIM (warnings spoilers, notes de
            # description du flow) : ignorées, elles n'ont pas de valeur de
            # dialogue.
            if _BOILERPLATE_LINE.match(stripped):
                continue
            if _KIM_POINTER_LINE.match(line):
                continue
            match = _BLOCKQUOTE_SPEAKER.match(stripped)
            if match:
                speaker = match.group("speaker").strip()
                text = match.group("text").strip()
                speaker = LoreStore._clean_kim_text(speaker)
                text = LoreStore._clean_kim_text(text)
                messages.append({
                    "index": index,
                    "speaker": speaker,
                    "text": text,
                    "player": LoreStore._is_player_speaker(speaker),
                })
            else:
                # ``> > choix`` : option de branche = saisie du joueur (KIM).
                nested = re.match(r"^>\s*>\s*(?P<text>.+)$", stripped)
                if nested:
                    messages.append({
                        "index": index,
                        "speaker": "",
                        "text": LoreStore._clean_kim_text(nested.group("text").strip()),
                        "player": True,
                    })
                elif stripped.startswith("> "):
                    # ``> texte`` sans locuteur : réplique anonyme (continuation).
                    text = LoreStore._clean_kim_text(stripped[2:].strip())
                    if text:
                        messages.append({
                            "index": index,
                            "speaker": "",
                            "text": text,
                            "player": False,
                        })
        return messages

    @staticmethod
    def spoiler_warning(content: str) -> str | None:
        """Avertissement spoiler d'une page KIM, si présent.

        Les pages KIM débutent par ``> *_SPOILERS_* _: <raison or Spoiler>_``.
        Retourne la raison (ou "Spoiler" par défaut), sinon ``None``.
        """
        for line in content.splitlines():
            m = _SPOILER_WARNING.match(line.strip())
            if m:
                reason = m.group("reason").strip().strip("_")
                return reason or "Spoiler"
        return None

    # ------------------------------------------------------ script simulateur
    @staticmethod
    def _norm_dialogue_ref(text: str) -> str:
        """Forme canonique d'une réplique pour résoudre les références de saut."""
        t = text.casefold()
        t = re.sub(r"\{p\s*\d+\}", " ", t)          # {P1}/{P2} : pauses de page
        t = re.sub(r"\{[^{}]*\}", " ", t)           # {…} (conditions, {Convo ends.})
        t = re.sub(r"^>+\s*", "", t)                # "> Ah" -> "Ah"
        t = re.sub(r"[.!?]+$", "", t)               # ponctuation finale
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def _build_kim_script(cls, content: str) -> list[dict]:
        """Script destiné au simulateur de messagerie KIM.

        Marche linéaire sur le walkthrough, enrichie par les métadonnées du
        script d'origine :

            * ``{Convo ends.}``   -> étape terminale (``ends``).
            * lignes ``> > ...``  -> regroupées en étape ``prompt`` (choix).
            * annotations parenthésées ``(...)`` -> ignorées (doublons déjà
              présents dans le fil linéaire).
            * annotations ``[Conversation continues as below, starting at
              "X"]`` / ``[Same as above from: "X"]`` -> ``jump_to`` résolue
              vers l'index d'étape cible (None si introuvable).

        Returns:
            Liste d'étapes ``{kind: "npc"|"prompt", speaker, text, player,
            options, ends, jump_to}``.
        """
        records = cls._parse_dialogue(content)
        # Classification des messages (index d'origine pour résolution saut).
        classified: list[tuple[int, str, dict, dict | None]] = []
        for orig_index, rec in enumerate(records):
            stripped = rec["text"].strip()
            surface = stripped.strip("*")   # "**(same as ...)**" -> "(same ...)"
            ends = bool(_CONVO_ENDS.search(stripped))
            scrubbed = _CONVO_ENDS.sub("", stripped).strip()
            if _ANNOT_PAREN.fullmatch(surface):
                # "(Choices same as ...)", "(Goes same as ...)", "(line required...)"
                classified.append((orig_index, "note", rec, None))
            elif surface.startswith("[") and surface.endswith("]"):
                if _JUMP_VAGUE.search(surface):
                    classified.append((orig_index, "note", rec, None))
                else:
                    jump = _JUMP_QUOTED.search(surface)
                    if jump:
                        ref = jump.group("below") or jump.group("above")
                        direction = "below" if jump.group("below") else "above"
                        classified.append(
                            (orig_index, "note", rec,
                             {"ref": ref, "dir": direction, "at": orig_index}))
                    else:
                        # "[...]" non reconnu -> didascalie, conservée.
                        classified.append((orig_index, "npc",
                                           {**rec, "text": scrubbed, "ends": ends}, None))
            elif not scrubbed:
                # Ligne ``{Convo ends.}`` seule : marqueur de fin.
                classified.append((orig_index, "term", rec, None))
            else:
                kind = "choice" if (rec["player"] and not rec["speaker"]) else "npc"
                classified.append((orig_index, kind,
                                   {**rec, "text": scrubbed, "ends": ends}, None))

        steps: list[dict] = []
        raw_to_step: list[int | None] = [None] * len(records)
        index = 0
        count = len(classified)
        while index < count:
            orig_index, kind, rec, meta = classified[index]
            if kind == "note":
                index += 1
                continue
            if kind == "term":
                if steps:
                    steps[-1]["ends"] = True
                index += 1
                continue
            if kind == "choice":
                options = []
                while index < count and classified[index][1] == "choice":
                    options.append({
                        "text": classified[index][2]["text"],
                        "ends": bool(classified[index][2].get("ends")),
                    })
                    raw_to_step[classified[index][0]] = len(steps)
                    index += 1
                steps.append({"kind": "prompt", "options": options,
                              "ends": False, "jump_to": None})
                continue
            # kind == "npc"
            step: dict = {
                "kind": "npc",
                "speaker": rec["speaker"],
                "text": rec["text"],
                "player": bool(rec["player"]),
                "ends": bool(rec.get("ends")),
                "jump_to": None,
            }
            steps.append(step)
            raw_to_step[orig_index] = len(steps) - 1
            index += 1

        # Résolution des sauts : la cible est référencée par texte normalisé.
        norm_to_origin: dict[str, list[int]] = {}
        for orig_index, rec in enumerate(records):
            key = cls._norm_dialogue_ref(rec["text"])
            if key:
                norm_to_origin.setdefault(key, []).append(orig_index)
        # L'annotation (posée après une réplique) pilote l'étape précédente :
        # ``anchor_step`` = dernière étape créée avant l'annotation.
        anchor_step: int | None = None
        for orig_index, kind, _rec, meta in classified:
            if kind == "term":
                continue
            if kind == "note":
                if meta is None or anchor_step is None:
                    continue
                key = cls._norm_dialogue_ref(meta["ref"])
                origins = norm_to_origin.get(key) or []
                if meta["dir"] == "below":
                    chosen = next((o for o in origins if o > meta["at"]), None)
                else:
                    chosen = origins[0] if origins else None
                target = raw_to_step[chosen] if chosen is not None else None
                if (target is not None and target != anchor_step
                        and steps[anchor_step]["kind"] == "npc"):
                    steps[anchor_step]["jump_to"] = target
            else:
                anchor_step = raw_to_step[orig_index]
        return steps

    # ---------------------------------------------------------------- recent
    def recent(self, limit: int = 20) -> list[dict]:
        """Pages triées par ``last_updated`` décroissant."""
        all_entries = []
        for bucket_id, entries in self._pages.items():
            for e in entries.values():
                all_entries.append((bucket_id, e))
        all_entries.sort(
            key=lambda pair: pair[1].get("last_updated", ""), reverse=True)
        recent = []
        for bucket_id, e in all_entries[:limit]:
            recent.append({
                "bucket_id": bucket_id,
                "page_title": e["page_title"],
                "canon_status": e.get("canon_status"),
                "last_updated": e.get("last_updated"),
            })
        return recent

    # ---------------------------------------------------------------- search
    def search(self, query: str, limit: int = 50, *,
               bucket: str | None = None, canon: str | None = None) -> list[dict]:
        """Recherche plein texte avec pondération stricte des titres.

        Hiérarchie absolue : toute page dont le *titre* contient la requête
        (insensible à la casse, partielle) est rendue en tête de liste, avant
        les simples mentions du terme dans le contenu.  Chaque résultat
        expose ``match_type`` (``title``/``content``) pour le regroupement
        visuel côté client.

        Args:
            query: terme recherché.
            limit: nombre max de résultats.
            bucket: restreindre à un bucket donné (id).
            canon: restreindre à un statut canon (canon/speculation/...).
        """
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for bucket_id, entries in self._pages.items():
            if bucket and bucket_id != bucket:
                continue
            for e in entries.values():
                if canon and e.get("canon_status") != canon:
                    continue
                content = e.get("content_markdown", "")
                if needle in e["page_title"].casefold():
                    title_hits.append(self._ranked_hit(
                        e, bucket_id, query, content, "title"))
                elif needle in content.casefold():
                    content_hits.append(self._ranked_hit(
                        e, bucket_id, query, content, "content"))
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
            "snippet": _make_snippet(content, query),
        }

    def suggest(self, query: str, limit: int = 8) -> list[dict]:
        """Autocomplétion : titres contenant ``query`` (+ contexte bucket).

        Hiérarchie identique à ``search`` : TOUTES les correspondances de
        titre de l'archive sont collectées avant les simples mentions
        (``match_type`` ``title`` vs ``content``), indépendamment de l'ordre
        des buckets — une page ``Hunhow/Quotes`` ne peut plus être noyée par
        les mentions des buckets antérieurs.
        """
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for bucket_id, entries in self._pages.items():
            bucket_title = self._buckets.get(bucket_id, {}).get("title", bucket_id)
            for e in entries.values():
                title = e["page_title"]
                title_hit = needle in title.casefold()
                content = e.get("content_markdown", "")
                content_hit = needle in content.casefold()
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
                        "snippet": _make_snippet(
                            content, query, radius=44),
                    })
        title_hits.sort(key=lambda r: (r["bucket_id"],
                                       r["page_title"].casefold()))
        content_hits.sort(key=lambda r: (r["bucket_id"],
                                         r["page_title"].casefold()))
        return (title_hits + content_hits)[:limit]

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict[str, Any]:
        total_pages = sum(len(e) for e in self._pages.values())
        total_chunks = 0  # Peut être extrapolé plus tard depuis SQL.
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
                (b["generated_at"] for b in self._buckets.values() if b["generated_at"]),
                default=None,
            ),
        }


def _make_snippet(content: str, query: str, radius: int = 60) -> str:
    """Extrait un extrait nettoyé autour du hit."""
    needle = query.casefold()
    position = content.casefold().find(needle)
    if position < 0:
        text = content[:2 * radius].strip()
    else:
        text = content[max(0, position - radius):position + radius].strip()
    # Nettoyage artefacts wiki
    text = re.sub(r"\|[-|]+\|?\s*", " ", text)      # |-|, ||, |||, |-
    text = re.sub(r"\{[^}]+\}", " ", text)           # {if...}, {Convo ends.}
    text = re.sub(r"_[^_]+_?", " ", text)            # _italique_
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"==[^=]+==", " ", text)           # ==highlight==
    text = re.sub(r"~{2}[^~]+~{2}", " ", text)      # ~~strike~~
    text = re.sub(r"\[[^\]]*\]", " ", text)          # [links / refs]
    text = re.sub(r"[|]", " ", text)                 # pipes résiduels
    text = re.sub(r"\s+", " ", text).strip()
    prefix = "…" if position > radius else ""
    suffix = "…" if 0 <= position < len(content) - radius else ""
    return prefix + text + suffix


# Marqueur terminal d'une conversation KIM.  Les données réelles utilisent
# ``{Convo ends.}`` (328 occurrences) contre ``{Convo. ends.}`` (3) et la
# coquille ``{Convoe ends.}`` (1) : on tolère l'absence de point et les
# variantes d'orthographe entre ``Convo`` et ``ends``.
_CONVO_ENDS = re.compile(r"\{[Cc]onvo[^}\n]{0,16}ends\.?\}", re.I)
_JUMP_ABOVE = re.compile(r"\[(?:Continues|Same) as above[,:]?\s*from:?\s*\"(?P<ref>[^\"]*)\",?\s*\]", re.I)
_JUMP_BELOW = re.compile(r"\[Goes the same as below choice\]", re.I)
_ANNOT_PAREN = re.compile(r"^\(\s*(?P<body>.*)\s*\)$", re.S)
_ANNOT_BRACKET = re.compile(r"^\[\s*(?P<body>.*)\s*\]$", re.S)
# Saut avec référence textuelle précise (``as below, starting at "X"`` /
# ``same as above, from "X"``) -> on peut résoudre la cible durant la marche.
_JUMP_QUOTED = re.compile(
    r"conversation\s+continues\s+as\s+below[,:]?\s+starting\s+at\s+"
    r"\"(?P<below>[^\"]*)\""
    r"|\bsame\s+as\s+above[,:]?\s+from:?\s+\"(?P<above>[^\"]*)\"",
    re.I)
# Annotations "Goes same as above/below choice" sans cible nommée : le doublon
# est déjà présent dans le fil linéaire -> on les ignore.
_JUMP_VAGUE = re.compile(
    r"\[goes\s+(?:the\s+)?same\s+as\s+(?:above|below(?:\s+choice)?|choice)\]",
    re.I)


def _slug_for_id(text: str) -> str:
    """Chaîne identifiant ASCII simple (alphabétique) depuis un texte."""
    return re.sub(r"[^A-Za-z0-9]+", "", text)


def _split_kim_conversations(page_title: str, content: str) -> list[dict]:
    """Découpe une page KIM en conversations distinctes.

    Chaque conversation est délimitée par un titre de section ``### …``
    (Wiki = ``=== … ===``), typiquement ``### Conversation 1 (sujet)``,
    éventuellement sous un en-tête de rang ``## Rank N - X``.  À l'instar de
    ``browse.wf``, on obtient ainsi des branches de dialogue indépendantes
    (id + titre) au lieu d'un seul graphe plat pour toute la page.

    Returns:
        Liste ordonnée de dicts ``{id, title, rank, body}`` où ``body`` est
        le Markdown de la conversation (titre de section inclus : les parseurs
        ``_build_dialogue_graph``/``_parse_dialogue`` s'en servent pour
        franchir leur préambule).
    """
    character = page_title.rsplit("/", 1)[-1].strip()
    head = _slug_for_id(character)
    lines = content.splitlines()

    segments: list[dict] = []
    pending: dict | None = None
    pending_start = 0
    rank_n: str = ""
    rank_display: str = ""

    def flush(end: int) -> None:
        nonlocal pending, pending_start
        if pending is None:
            return
        pending["body"] = "\n".join(lines[pending_start:end]).rstrip()
        segments.append(pending)
        pending = None
        pending_start = end

    for index, line in enumerate(lines):
        stripped = line.strip()
        rank_match = _KIM_RANK_TITLE.match(stripped)
        if rank_match:
            flush(index)
            rank_n = rank_match.group("n")
            rank_display = (f"Rank {rank_n} - "
                            f"{rank_match.group('label').strip()}")
            continue
        section_match = _KIM_SECTION_TITLE.match(stripped)
        if section_match:
            flush(index)
            section_title = section_match.group("title").strip()
            base_id = f"{head}Rank{rank_n}" if rank_n else head
            convo = _KIM_CONVO_NUMBER.match(section_title)
            if convo:
                base_id += f"Convo{convo.group(1)}"
            else:
                base_id += _slug_for_id(section_title)
            pending = {
                "id": base_id,
                "title": section_title,
                "rank": rank_display,
            }
            pending_start = index
    flush(len(lines))

    # Garantit l'unicité des identifiants (titres/toute numérotation répétés).
    seen: set[str] = set()
    for segment in segments:
        base = segment["id"]
        if base in seen:
            suffix = 2
            while f"{base}-{suffix}" in seen:
                suffix += 1
            segment["id"] = f"{base}-{suffix}"
        seen.add(segment["id"])
    return segments


def _build_dialogue_graph(content: str, root_label: str | None = None) -> dict:
    """Construit le graphe de conversation (nœuds + arêtes) d'une page KIM.

    Sémantique des nœuds :
        * nœud PNJ   -> ``speaker`` = nom du personnage (bordure bleue).
        * nœud joueur-> ``player`` = True (choix ``> >``, bordure rouge).
        * nœud mixte (``> texte`` anonyme, continuation) -> pas de locuteur.
        * ``root_label`` (optionnel) -> un nœud-système unique est injecté en
          tête (``_anchor_graph``) : tous les nœuds sans arête entrante y sont
          rattachés, garantissant une racine unique (pyramide TB).

    Sémantique des arêtes :
        * flux séquentiel normal d'un nœud vers le suivant ;
        * chaque choix ``> >`` est une OPTION qui part du dernier nœud PNJ
          (même si ce dernier est marqué ``{Convo. ends}``) ;
        * ``{Convo. ends}`` marque un nœud terminal (plus d'arête sortante) ;
        * annotations ``[Continues/Same as above...]`` / ``[Goes the same as
          below choice]`` ajoutent des arêtes de saut vers le nœud référencé.
    """
    lines = content.splitlines()
    nodes: list[dict] = []
    edges: list[dict] = []
    by_text: dict[str, str] = {}   # texte normalisé -> id de nœud (récits)
    last_npc: str | None = None     # dernier nœud PNJ
    pending_choices: list[str] = []  # options en attente de la suite PNJ
    in_preamble = True  # skip la "note d'en-tête" (spoilers, description)

    def add_node(kind: str, speaker: str, text: str, player: bool) -> str:
        prefix = "c_" if kind == "choice" else "n_"
        nid = f"{prefix}{len(nodes)}"
        ends = bool(_CONVO_ENDS.search(text))
        scrubbed = LoreStore._clean_kim_text(_CONVO_ENDS.sub("", text))
        nodes.append({
            "id": nid,
            "speaker": LoreStore._clean_kim_text(speaker),
            "text": scrubbed,
            "player": player,
            "terminal": ends,
        })
        key = _norm_ref(text)
        if key and key not in by_text:
            by_text[key] = nid
        return nid

    def link(source: str, target: str, label: str = "", force: bool = False) -> None:
        if not source or not target or source == target:
            return
        # Un nœud terminal (``{Convo. ends}``) n'a jamais d'arête sortante,
        # SAUF vers les options du joueur qui le suivent (``force=True``) :
        # sans ça, ces choix deviennent des racines orphelines dans le layou
        # (propulsés tout en haut, côte à côte).
        if not force and nodes_id_last_terminal(nodes, source):
            return
        edges.append({"source": source, "target": target, "label": label})

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        # Saute le préambule (notes d'en-tête : spoilers, description du flow)
        # jusqu'à la première section ``##``/``###`` qui commence la conversation.
        if in_preamble:
            if stripped.startswith("## ") or stripped.startswith("### "):
                in_preamble = False
            else:
                continue
        ann = _JUMP_ABOVE.search(stripped)
        if ann:
            ref = ann.group("ref")
            target = by_text.get(_norm_ref(ref))
            if target and last_npc:
                link(last_npc, target, "↻")
            continue
        if _JUMP_BELOW.search(stripped):
            redirect_to_choices = True
            continue

        # Pointeur de navigation KIM (``{Continues/Same/Jump ...}``) : le
        # contenu répète la branche référencée -> ligne ignorée.
        if _KIM_POINTER_LINE.match(stripped):
            continue

        match = _BLOCKQUOTE_SPEAKER.match(stripped)
        if match:
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            nid = add_node("npc", speaker, text,
                           player=LoreStore._is_player_speaker(speaker))
            # Les options en attente se rejoignent sur cette nouvelle réplique PNJ.
            for opt in pending_choices:
                link(opt, nid)
            had_choices = bool(pending_choices)
            pending_choices = []
            # Pas d'arête directe quand des options étaient en attente : la
            # continuité passe par les choix (sinon arête de contournement).
            if (last_npc and not had_choices
                    and not nodes_id_last_terminal(nodes, last_npc)):
                link(last_npc, nid)
            last_npc = nid
            continue

        nested = re.match(r"^>\s*>\s*(?P<text>.+)$", stripped)
        if nested:
            nid = add_node("choice", "", nested.group("text").strip(), player=True)
            origin = last_npc
            if origin:
                link(origin, nid, force=True)
            elif pending_choices:
                link(pending_choices[-1], nid)
            pending_choices.append(nid)
            continue

        if stripped.startswith("> "):
            text = stripped[2:].strip()
            if text:
                nid = add_node("npc", "", text, player=False)
                for opt in pending_choices:
                    link(opt, nid)
                had_choices = bool(pending_choices)
                pending_choices = []
                # Pas d'arête directe quand des options étaient en attente.
                if (last_npc and not had_choices
                        and not nodes_id_last_terminal(nodes, last_npc)):
                    link(last_npc, nid)
                last_npc = nid

    graph = {"nodes": nodes, "edges": edges}
    if root_label:
        graph = _anchor_graph(nodes, edges, root_label)
    return graph


def nodes_id_last_terminal(nodes: list[dict], nid: str) -> bool:
    for n in nodes:
        if n["id"] == nid:
            return bool(n.get("terminal"))
    return False


def _norm_ref(text: str) -> str:
    """Normalise une chaîne pour la résolution des renvois (sauts)."""
    out = _CONVO_ENDS.sub("", text)
    out = re.sub(r"\s+", " ", out).strip().strip("*").strip()
    return out.lower()[:120]
class ApiHandler(BaseHTTPRequestHandler):
    server_version = "CephalonUI/1.0"
    store: LoreStore = None  # injecté par la fabrique
    media: MediaIndex = None  # injecté par la fabrique
    root: Path = None        # répertoire des fichiers statiques

    # ------------------------------------------------------------ verbosité
    def log_message(self, format, *args):  # noqa: A002  (signature stdlib)
        return  # silencieux ; les logs passent par le lanceur.

    # ---------------------------------------------------------------- routes
    def do_GET(self) -> None:
        path, _, query_raw = self.path.partition("?")
        query = parse_qs(query_raw)
        if path.startswith("/api/"):
            self.store.maybe_reload()
        try:
            if path in ("/", "/index.html"):
                self._send_static("index.html")
            elif path == "/app.js":
                self._send_static("app.js", content_type="text/javascript")
            elif path == "/styles.css":
                self._send_static("styles.css", content_type="text/css")
            elif path == "/vendor/vue-flow.bundle.js":
                self._send_static("vendor/vue-flow.bundle.js", content_type="text/javascript")
            elif path == "/vendor/vue-flow.bundle.css":
                self._send_static("vendor/vue-flow.bundle.css", content_type="text/css")
            elif path == "/api/stats":
                self._send_json(self.store.stats())
            elif path == "/api/buckets":
                self._send_json(self.store.list_buckets())
            elif path == "/api/pages":
                self._send_json(self._pages_for_query(query))
            elif path == "/api/page":
                self._send_json(self._page_for_query(query))
            elif path == "/api/kim":
                self._send_json(self._kim_for_query(query))
            elif path == "/api/graph":
                title = unquote((query.get("title") or [""])[0])
                conv = unquote((query.get("conv") or [""])[0])
                self._send_json(self.store.kim_graph(title, conv) or {})
            elif path == "/api/recent":
                limit = _int_from_query(query, "limit", 20)
                self._send_json(self.store.recent(limit=limit))
            elif path == "/api/search":
                q = (query.get("q") or [""])[0]
                limit = _int_from_query(query, "limit", 50)
                bucket = (query.get("bucket") or [""])[0] or None
                canon = (query.get("canon") or [""])[0] or None
                self._send_json(self.store.search(
                    q, limit=limit, bucket=bucket, canon=canon))
            elif path == "/api/suggest":
                q = (query.get("q") or [""])[0]
                limit = _int_from_query(query, "limit", 8)
                self._send_json(self.store.suggest(q, limit=limit))
            elif path == "/api/media":
                self._send_json(self._media_payload())
            elif path.startswith("/media/"):
                self._send_media(unquote(path.rsplit("/", 1)[-1]))
            else:
                self._send_json({"error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001  (réponse 500 générique)
            try:
                self._send_json({"error": str(exc)}, status=500)
            except OSError:
                pass

    # -------------------------------------------------------------- helpers
    def _pages_for_query(self, query) -> list[dict]:
        bucket = (query.get("bucket") or [""])[0]
        if not bucket or not self.store.bucket_exists(bucket):
            return []
        return self.store.list_pages(bucket)

    def _page_for_query(self, query) -> dict | None:
        bucket = (query.get("bucket") or [""])[0]
        title = unquote((query.get("title") or [""])[0])
        if bucket and not self.store.bucket_exists(bucket):
            return None
        if self.store.bucket_exists(bucket):
            return self.store.get_page(bucket, title)
        return self.store.get_dialogue_page(title)

    def _kim_for_query(self, query) -> list[dict] | dict:
        title = unquote((query.get("title") or [""])[0])
        conv = unquote((query.get("conv") or [""])[0])
        mode = (query.get("mode") or [""])[0]
        if not title:
            return self.store.kim_pages()
        page = self.store.get_dialogue_page(title)
        content = (page or {}).get("content_markdown", "")
        if not page or not self.store._looks_like_dialogue(content):
            return {"character": None, "spoiler": None, "conversations": []}
        if not conv:
            conversations = self.store.kim_conversations(title)
            return {
                "character": title.rsplit("/", 1)[-1],
                "spoiler": self.store.spoiler_warning(content),
                "conversations": [
                    {"id": c["id"], "title": c["title"],
                     "rank": c["rank"], "source": c.get("source", "wiki")}
                    for c in conversations
                ],
            }
        for conversation in self.store.kim_conversations(title):
            if conversation["id"] != conv:
                continue
            result = {
                "id": conversation["id"],
                "title": conversation["title"],
                "rank": conversation["rank"],
            }
            character = title.rsplit("/", 1)[-1].strip()
            dm_detail = self.store.kim_dm.conversation(character, conv)
            if mode == "sim":
                if dm_detail is not None:
                    result["script"] = dm_detail["script"]
                else:
                    result["script"] = self.store._build_kim_script(
                        conversation["body"])
                result["spoiler"] = self.store.spoiler_warning(content)
            else:
                if dm_detail is not None:
                    result["messages"] = dm_detail["messages"]
                else:
                    result["messages"] = self.store._parse_dialogue(
                        conversation["body"])
                result["source"] = dm_detail["source"] if dm_detail else "wiki"
            return result
        return {"id": None, "title": None, "rank": None, "messages": []}

    def _send_static(self, filename: str, content_type: str = "text/html") -> None:
        static_file = (self.root / filename) if self.root else Path(filename)
        if not static_file.is_file():
            self._send_json({"error": f"Static file '{filename}' not found"},
                            status=404)
            return
        raw = static_file.read_bytes()
        compressed = gzip.compress(raw)
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(compressed)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(raw)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(compressed)

    # ---------------------------------------------------------------- média
    def _media_payload(self) -> dict:
        media = self.media
        if media is None:
            return {"available": False, "count": 0,
                    "titles": {}, "speakers": {}, "buckets": {}}
        media.ensure()
        if not media.available():
            return {"available": False, "count": 0,
                    "titles": {}, "speakers": {}, "buckets": {}}
        return media.media_payload(
            page_titles_by_bucket=self.store.page_titles_by_bucket(),
            speakers=self.store.kim_speakers(),
        )

    def _send_media(self, filename: str) -> None:
        media = self.media
        if media is None or not filename:
            self._send_json({"error": "Not found"}, status=404)
            return
        media.ensure()
        if not media.available():
            self._send_json({"error": "Not found"}, status=404)
            return
        payload = media.fetch_image(filename)
        if payload is None:
            self._send_json({"error": "Image introuvable"}, status=404)
            return
        content_type = "image/png"
        if filename.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".gif"):
            content_type = "image/gif"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(payload)


def _int_from_query(query: dict, key: str, default: int) -> int:
    value = (query.get(key) or [None])[0]
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


# --------------------------------------------------------------------------
# Lancement.
# --------------------------------------------------------------------------
def _bundle_root() -> Path:
    """Racine des fichiers dépaquetés PyInstaller (``sys._MEIPASS``)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent


def _static_dir() -> Path:
    """Répertoire des fichiers statiques (source, sdist ou exe PyInstaller)."""
    root = _bundle_root()
    for candidate in (
        root / "warframe_lore" / "ui" / "static",   # exe onefile --add-data
        root / "static",                            # paquet installé / source
        Path(__file__).resolve().parent / "static",
    ):
        if candidate.is_dir():
            return candidate
    return root


def _default_output_dir() -> Path:
    """Dossier de megafiles à exposer : le ``out/`` du répertoire courant s'il
    existe, sinon celui du projet (source), sinon à côté de l'exe, sinon
    l'attendu de l'exe."""
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    candidates = [
        Path.cwd() / "out",
        Path(__file__).resolve().parent.parent.parent / "out",
        *( [exe_dir / "out"] if exe_dir else [] ),
        _bundle_root() / "out",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def serve_forever(output_dir: Path, port: int = 0,
                  open_browser: bool = True) -> None:
    """Démarre le serveur (bloquant). Utilisé par ``cephalon ui``.

    Args:
        output_dir: dossier des megafiles à exposer.
        port: port à utiliser (0 = port libre automatique).
        open_browser: ouvrir le navigateur par défaut après démarrage.
    """
    store = LoreStore(output_dir)
    media = MediaIndex(output_dir, cache_dir="cache/public_export/media")
    handler = _build_handler(store, media)
    try:
        threading.Thread(target=media.ensure, daemon=True).start()
    except RuntimeError:  # pas de thread disponible : construction au 1er appel
        pass
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    actual_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    print(f"Cephalon UI — interface disponible sur {url}")
    print(f"  Source de données : {output_dir.resolve()}")
    print("  Pressez Ctrl+C pour arrêter le serveur.")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de Cephalon UI.")
    finally:
        httpd.server_close()
        print("Serveur arrêté.")


def _build_handler(store: LoreStore, media: MediaIndex | None = None) -> type[ApiHandler]:
    ApiHandler.store = store
    ApiHandler.media = media
    ApiHandler.root = _static_dir()
    return ApiHandler


def main(argv: list[str] | None = None) -> int:
    """Entry point console ``cephalon-ui`` (autonome, pour l'exe PyInstaller)."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="cephalon-ui",
        description="Interface web pour parcourir le lore Warframe récupéré.",
    )
    parser.add_argument("--out", type=Path, default=None,
                        help="Dossier des megafiles (défaut: ./out)")
    parser.add_argument("--port", type=int, default=0,
                        help="Port à utiliser (0 = libre, défaut)")
    parser.add_argument("--no-browser", action="store_true",
                        help="N'ouvre pas le navigateur automatiquement.")
    args = parser.parse_args(argv)

    output_dir = args.out or _default_output_dir()
    if not output_dir.is_dir():
        print(f"Attention : aucun dossier de données trouvé ({output_dir}).")
        print("Lancez d'abord `cephalon run` pour générer les megafiles.")
    serve_forever(output_dir, port=args.port,
                  open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())