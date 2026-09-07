"""Machine à états de suppression des blocs gameplay (lore imbriqué gardé)."""

# But : une page de quête contient des sections "Acquisition", "Stats',
# "Patch history" (gameplay, bruit) et des sections "Lore", "Summary",
# "Dialogue" (essentielles). On supprime les blocs gameplay, SAUF si un bloc
# gameplay contient une sous-section lore imbriquée (cas de ``Trivia``
# contenant du lore).
#
# La logique travaille ligne à ligne sur le texte déjà transformé en Markdown
# (titres ``## ...``) pour préserver la structure finale.

from __future__ import annotations

import re

from warframe_lore.cleaner.config import CleanerConfig
from warframe_lore.cleaner.sections_classify import (
    is_gameplay_section,
    is_lore_section,
)

_HEADING_PATTERN = re.compile(r"^(={2,6}|#{1,6})\s*(.*?)\s*(?:={0,2}|#*)\s*$")


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


__all__ = ["drop_gameplay_sections"]