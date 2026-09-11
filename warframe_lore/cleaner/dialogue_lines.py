"""Indentation and dialogue lines -> readable Markdown blockquotes."""

from __future__ import annotations

import re

from warframe_lore.cleaner.bullets import BULLET_TOKEN, _BULLET_LINE


def normalise_indentation(markdown_text: str) -> str:
    """Removes Wikitext indentation markers (:, #, ;).

    ``:`` and ``;`` are dropped (often leftover artifacts), numbered lists
    ``#`` become bullet ``- `` items.
    """
    text = markdown_text
    text = re.sub(r"^:+\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#(?=\s|\d)", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^;\s*", "", text, flags=re.MULTILINE)
    return text


def format_lists_and_dialogue(markdown_text: str) -> str:
    """Converts dialogue lines into readable ``> `` blockquotes.

    Detects our BULLET_TOKEN-protected bullets; the pattern
    ``Character: line`` becomes ``> **Character:** line``.
    """
    lines = markdown_text.split("\n")
    output_lines: list[str] = []
    inside_dialogue_block = False

    for line in lines:
        stripped_line = line.strip()

        if _BULLET_LINE.match(stripped_line):
            dialogue_content = stripped_line[len(BULLET_TOKEN):].strip()
            # Strip remaining markers and outer quotes.
            dialogue_content = re.sub(r"\*\*+|_+", "", dialogue_content)
            dialogue_content = re.sub(r'^"|"$', "", dialogue_content.strip())
            output_lines.append(_format_dialogue_line(dialogue_content))
            inside_dialogue_block = True

        elif stripped_line:
            if inside_dialogue_block:
                output_lines.append("")  # separator line after dialogue
            inside_dialogue_block = False
            output_lines.append(line)

        else:
            inside_dialogue_block = False

    return "\n".join(output_lines)


def _format_dialogue_line(dialogue_content: str) -> str:
    """A dialogue line -> blockquote, with speaker/line separation."""
    if ":" in dialogue_content:
        speaker, rest_of_line = dialogue_content.split(":", 1)
        clean_rest = re.sub(r'^"|"$', "", rest_of_line.strip())
        return f"> **{speaker.strip()}:** {clean_rest}"
    return f"> {dialogue_content.strip()}"


__all__ = ["normalise_indentation", "format_lists_and_dialogue"]
