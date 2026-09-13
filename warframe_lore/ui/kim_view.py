"""KIM view — dialogue projections over the loaded corpus.

Single responsibility: expose the KIM pages, their speakers, conversations,
raw markdown, flowcharts and line-level dialogue from the store's buckets.
The fine parsing lives in ``dialogue*``; here only coherent accessors.
"""

from __future__ import annotations

from . import dialogue as dlg
from .dialogue_graph import build_dialogue_graph
from .dialogue_script import build_kim_script


class KimViewMixin:
    """Accès KIM : locuteurs, pages, conversations, graphes, scripts."""

    def kim_speakers(self) -> list[str]:
        """Locuteurs rencontrés dans le Terminal KIM (ordre d'apparition)."""
        seen: list[str] = []
        for entry in self._pages.get(dlg.KIM_BUCKET_ID, {}).values():
            for speaker in dlg.speakers(entry.get("content_markdown", "")):
                if speaker not in seen:
                    seen.append(speaker)
        return seen

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

    @classmethod
    def _parse_dialogue(cls, content: str) -> list[dict]:
        return dlg.parse_dialogue(content)

    @staticmethod
    def spoiler_warning(content: str) -> str | None:
        return dlg.spoiler_warning(content)

    @classmethod
    def _build_kim_script(cls, content: str) -> list[dict]:
        return build_kim_script(content)
