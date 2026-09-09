"""State machine for dropping gameplay blocks (nested lore kept).

Goal: a quest page contains "Acquisition", "Stats",
"Patch history" sections (gameplay, noise) and "Lore", "Summary",
"Dialogue" sections (essential).  We drop gameplay blocks, UNLESS a
gameplay block contains a nested lore subsection (case of ``Trivia``
containing lore).

The logic works line-by-line on text already converted to Markdown
(``## ...`` headings) to preserve the final structure.
"""

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
    """Drops gameplay sections while preserving nested lore.

    Uses a state machine: as long as we are inside a gameplay block,
    lines are ignored; a lore subsection triggers early exit from the block.
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
                # We are inside a gameplay block: exit if nested lore
                # or if we rise back to the suppressed block's level.
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
                continue  # discard the gameplay heading

            output_lines.append(line)
        elif not suppression_active_at_level:
            output_lines.append(line)

    return "\n".join(output_lines)


__all__ = ["drop_gameplay_sections"]
