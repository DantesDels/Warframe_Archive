"""Indentation et lignes de dialogue -> blockquotes Markdown lisibles."""

from __future__ import annotations

import re

from warframe_lore.cleaner.bullets import BULLET_TOKEN, _BULLET_LINE


def normalise_indentation(markdown_text: str) -> str:
    """Supprime les marqueurs d'indentation Wikitext (:, #, ;).

    ``:`` et ``;`` disparaissent (souvent vestiges), les listes numérotées
    ``#`` deviennent des puces ``- ``.
    """
    text = markdown_text
    text = re.sub(r"^:+\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#(?=\s|\d)", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^;\s*", "", text, flags=re.MULTILINE)
    return text


def format_lists_and_dialogue(markdown_text: str) -> str:
    """Transforme les lignes de dialogue en blockquotes ``> `` lisibles.

    Détecte nos puces protégées par BULLET_TOKEN ; le pattern
    ``Personnage: réplique`` devient ``> **Personnage:** réplique``.
    """
    lines = markdown_text.split("\n")
    output_lines: list[str] = []
    inside_dialogue_block = False

    for line in lines:
        stripped_line = line.strip()

        if _BULLET_LINE.match(stripped_line):
            dialogue_content = stripped_line[len(BULLET_TOKEN):].strip()
            # Retire les marqueurs restants et les guillemets externes.
            dialogue_content = re.sub(r"\*\*+|_+", "", dialogue_content)
            dialogue_content = re.sub(r'^"|"$', "", dialogue_content.strip())
            output_lines.append(_format_dialogue_line(dialogue_content))
            inside_dialogue_block = True

        elif stripped_line:
            if inside_dialogue_block:
                output_lines.append("")  # ligne de démarcation après dialogue
            inside_dialogue_block = False
            output_lines.append(line)

        else:
            inside_dialogue_block = False

    return "\n".join(output_lines)


def _format_dialogue_line(dialogue_content: str) -> str:
    """Une ligne de dialogue -> blockquote, avec séparation locuteur/réplique."""
    if ":" in dialogue_content:
        speaker, rest_of_line = dialogue_content.split(":", 1)
        clean_rest = re.sub(r'^"|"$', "", rest_of_line.strip())
        return f"> **{speaker.strip()}:** {clean_rest}"
    return f"> {dialogue_content.strip()}"


__all__ = ["normalise_indentation", "format_lists_and_dialogue"]