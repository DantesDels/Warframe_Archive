"""Coupe du bruit de bas de page (navboxes, catégories, historique Update)."""

from __future__ import annotations

import re

# Lignes exactes de métadonnées rendues en texte brut par les navboxes Wiki,
# typiquement en fin de page : ``Quotes`` puis ``quotesnav``, ou ``Sentient``
# pour les pages liées aux Sentients.
_FOOTER_METADATA_LINE = re.compile(r"^(?:quotesnav|quotes|sentient)$", re.I)
# Historique de mise à jour : ``Update 27.2``… (bruit, non canon) — le format
# structuré ``[{version, notes}]`` est déjà extrait ailleurs (patch notes).
_HISTORY_LINE = re.compile(r"^update\s+\d+", re.I)


def cut_footer_noise(markdown_text: str) -> str:
    """Tronque tout ce qui suit la première ligne de bas de page.

    Dès qu'une ligne correspond exactement à un mot-clé de navbox/catégorie
    (``quotesnav``, ``Quotes``, ``Sentient``) ou à un historique ``Update N``,
    l'ensemble du texte restant est du bruit de scrape (navboxes, catégories) :
    on ignore et on tronque.  Correspondance sur ligne exacte (une seule).
    """
    lines = markdown_text.split("\n")
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        if _FOOTER_METADATA_LINE.match(stripped) or _HISTORY_LINE.match(stripped):
            # Index 0 = en-tête artefact (ex: ``Sentient`` au-dessus d'une page
            # ``Damage/Sentient``) : tronquer toute la page serait pire.
            if i == 0:
                return markdown_text
            return "\n".join(lines[:i]).rstrip() + "\n"
    return markdown_text


__all__ = ["cut_footer_noise"]