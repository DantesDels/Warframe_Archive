"""Filtrage des sections par en-tête (gameplay vs narratif).

But : une page de quête contient des sections "Acquisition", "Stats',
"Patch history" (gameplay, bruit) et des sections "Lore", "Summary",
"Dialogue" (essentielles).  On supprime les blocs gameplay, SAUF si un
bloc gameplay contient une sous-section lore imbriquée (cas de
``Trivia`` contenant du lore).

La logique travaille ligne à ligne sur le texte déjà transformé en
Markdown (titres ``## ...``) pour préserver la structure finale.
"""

from __future__ import annotations

import re

from . import CleanerConfig

_HEADING_PATTERN = re.compile(r"^(={2,6}|#{1,6})\s*(.*?)\s*(?:={0,2}|#*)\s*$")


def _normalize_for_comparison(value_to_normalize: str) -> str:
    """Minuscules, sans caractères spéciaux (comparaison fiable).

    Appliqué AUX DEUX termes de la comparaison (titre et mots-clés), sinon
    ``"trivia (gameplay)"`` ne peut jamais correspondre à ``"Trivia (gameplay)"``
    normalisé en ``"trivia gameplay"``.
    """
    return re.sub(r"[^a-z0-9 ]", "", value_to_normalize.lower())


def is_gameplay_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le titre de section relève du gameplay (stats, builds, ...)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.gameplay_exclude)


def is_lore_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le titre de section est clairement narratif (lore, histoire)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.lore_keep)


def drop_gameplay_sections(markdown_text: str,
                           cleaner_config: CleanerConfig) -> str:
    """Supprime les sections gameplay tout en conservant le lore imbriqué.

    Uses a state machine : tant qu'on est dans un bloc gameplay, on ignore
    les lignes ; une sous-section lore ouvre la sortie prématurée du bloc.
    """
    lines = markdown_text.split("\n")
    output_lines: list[str] = []
    suppression_active_at_level = 0

    for line in lines:
        heading_match = _HEADING_PATTERN.match(line)
        is_heading = heading_match is not None

        if is_heading:
            heading_level = len(heading_match.group(1))
            heading_title = heading_match.group(2)
            is_lore_heading = is_lore_section(heading_title, cleaner_config)
            is_gameplay_heading = is_gameplay_section(heading_title, cleaner_config)

            if suppression_active_at_level:
                # On est sous un bloc gameplay : on ressort si lore imbriqué
                # ou si on remonte au niveau du bloc supprimé.
                if is_lore_heading:
                    suppression_active_at_level = 0
                elif heading_level <= suppression_active_at_level:
                    suppression_active_at_level = 0
                else:
                    output_lines.append(line)
                    continue

            if not suppression_active_at_level and is_gameplay_heading \
                    and not is_lore_heading:
                suppression_active_at_level = heading_level
                continue  # on jette l'en-tête gameplay

            output_lines.append(line)
        elif not suppression_active_at_level:
            output_lines.append(line)

    return "\n".join(output_lines)