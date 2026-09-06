"""Extraction des dialogues KIM depuis le Markdown nettoyé.

Les pages KIM (``Kinemantik Instant Messenger``) sont rendues par le
cleaner sous forme de blockquotes lisibles :
    ``> **Amir:** Salut Tenno, t'as vu le nouveau graff ?``
    ``> **Arthur:** ...``

Ce module convertit ce rendu en lignes structurées pour la table
``kim_dialogues`` (locuteur + texte + ordre chronologique).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Format gras (sortie du cleaner) : '> **Amir:** texte'.
# NB : le deux-points est DANS le gras (``**Amir:**`` = ``**`` + ``Amir:`` + ``**``).
_KIM_BOLD_LINE_PATTERN = re.compile(
    r"^>\s*\*\*(?P<line>[^*]+?)\*\*\s*(?P<text>.*)$"
)
# Format simple : '> Amir : texte' (fallback).
_KIM_PLAIN_LINE_PATTERN = re.compile(
    r"^>\s*(?P<speaker>[^:]+?)\s*:\s*(?P<text>.*)$"
)
# Option de branche KIM (choix du joueur) : '> > choix texte'.
_KIM_CHOICE_LINE_PATTERN = re.compile(r"^>\s*>\s*(?P<text>.+)$")


@dataclass(frozen=True)
class KimMessage:
    """Un message structuré extrait d'une discussion KIM."""

    message_order: int
    speaker: str
    message_text: str
    timestamp: str | None = None
    player_choice: bool = False


def extract_kim_messages(markdown_text: str) -> list[KimMessage]:
    """Extrait les messages KIM structurés d'un Markdown nettoyé.

    Retourne ``[]`` si le texte ne contient aucune ligne de dialogue au
    format attendu.  L'ordre retourné correspond à l'ordre d'apparition.
    """
    messages: list[KimMessage] = []
    for line in markdown_text.split("\n"):
        stripped_line = line.strip()
        match = _KIM_BOLD_LINE_PATTERN.match(stripped_line)
        if match is not None:
            bolded_segment = match.group("line")
            speaker_name, _, _ = bolded_segment.rpartition(":")
            speaker_name = speaker_name.strip()
            message_text = match.group("text").strip()
            player_choice = False
        else:
            # ``> > option`` : choix de branche = saisie du joueur (KIM).
            choice = _KIM_CHOICE_LINE_PATTERN.match(stripped_line)
            if choice is not None:
                choice_text = choice.group("text").strip()
                if choice_text:
                    messages.append(KimMessage(
                        message_order=len(messages),
                        speaker="",
                        message_text=choice_text,
                        timestamp=None,
                        player_choice=True,
                    ))
                continue
            match = _KIM_PLAIN_LINE_PATTERN.match(stripped_line)
            if match is None:
                continue
            speaker_name = match.group("speaker").strip()
            message_text = match.group("text").strip()
            player_choice = False
        if not speaker_name or not message_text:
            continue
        # Filtre les artefacts du cleaner (blockquotes de spoiler, etc.) : un
        # vrai nom de locuteur ne contient ni '*' ni '_' ni de balises.
        if not _looks_like_speaker_name(speaker_name):
            continue
        messages.append(KimMessage(
            message_order=len(messages),
            speaker=speaker_name,
            message_text=message_text,
            timestamp=None,
            player_choice=player_choice,
        ))
    return messages


def _looks_like_speaker_name(candidate: str) -> bool:
    """Vrai si le 'locuteur' ressemble à un personnage KIM plausible.

    Exclut les artefacts de mise en forme (``*_SPOILERS_* _``, ``**[...]``)
    qui n'ont pas de nom propre.
    """
    if any(marker in candidate for marker in ("*", "_", "]", "}")):
        return False
    return candidate[0].isalpha() and candidate[0].isupper()