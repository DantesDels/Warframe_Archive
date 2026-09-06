"""Mise en forme finale du texte Markdown.

Responsabilités :
  * liens internes/externes -> texte lisible ;
  * wikitext gras/italique -> Markdown équivalent ;
  * protection des puces avant conversion (sentinelle) ;
  * reflow des titres ``== X ==`` -> ``## X`` ;
  * normalisation de l'indentation ;
  * mise en forme des dialogues (quotations lisibles).

Chaque fonction est pure (``str -> str``) et testable isolément.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Sentinelle protégeant les puces Wikitext ("* ...") avant la conversion
# en Markdown, pour que le caractère '*' ne collisionne pas avec "**bold**".
# ---------------------------------------------------------------------------
BULLET_TOKEN = "\x00BULLET\x00"
_LEADING_BULLETS = re.compile(r"^(\*+)(.*)$", re.MULTILINE)
_BULLET_LINE = re.compile(r"^\s*" + re.escape(BULLET_TOKEN))
_HEADING_WIKI = re.compile(r"^(={2,})(.*?)(?:={2,}|$)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Titres.
# ---------------------------------------------------------------------------
def reflow_headings_to_markdown(wikitext: str) -> str:
    """Convertit ``== Titre ==`` en ``## Titre`` (niveau limité à 6)."""

    def _heading_replacement(match: re.Match) -> str:
        heading_equals_count = match.group(1).count("=")
        heading_title = match.group(2).strip()
        markdown_level = min(heading_equals_count, 6)
        return f"\n\n{'#' * markdown_level} {heading_title}\n"

    return _HEADING_WIKI.sub(_heading_replacement, wikitext)


# ---------------------------------------------------------------------------
# Conservatoire des puces.
# ---------------------------------------------------------------------------
def protect_bullets(wikitext: str) -> str:
    """Remplace les puces de début de ligne par la sentinelle BULLET_TOKEN."""
    def _replace_bullet_line(match: re.Match) -> str:
        return BULLET_TOKEN + match.group(2).lstrip()

    return _LEADING_BULLETS.sub(_replace_bullet_line, wikitext)


# ---------------------------------------------------------------------------
# Conversion gras/italique.
# ---------------------------------------------------------------------------
def convert_markup_to_markdown(wikitext: str) -> str:
    """Convertit ''italique'' / '''gras''' / '''''gras-italique''''' en Markdown.

    Ordre critique : gras-italique (5 apostrophes) d'abord, puis gras (3),
    puis italique (2), pour éviter des appariements incorrects.
    """
    text = wikitext
    text = re.sub(r"'''''(.*?)'''''", r"**_\1_**", text)  # gras + italique
    text = re.sub(r"'''(.*?)'''", r"**\1**", text)        # gras
    text = re.sub(r"''(.*?)''", r"_\1_", text)            # italique
    return text


# ---------------------------------------------------------------------------
# Liens.
# ---------------------------------------------------------------------------
_INTERNAL_LINK_PIPED = re.compile(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]")
_INTERNAL_LINK_PLAIN = re.compile(r"\[\[([^\[\]]*)\]\]")
_EXTERNAL_LINK_LABELED = re.compile(r"\[(https?://[^\s\[\]]+)\s+([^\]]+)\]")
_EXTERNAL_LINK_RAW = re.compile(r"\[(https?://[^\s\[\]]+)\]")


def normalise_links(wikitext: str) -> str:
    """Transforme les liens en texte de lecture : [[Cible|Label]] -> Label."""
    text = wikitext
    text = _INTERNAL_LINK_PIPED.sub(_replace_piped_link, text)
    text = _INTERNAL_LINK_PLAIN.sub(_replace_plain_link, text)
    text = _EXTERNAL_LINK_LABELED.sub(r"\2", text)
    text = _EXTERNAL_LINK_RAW.sub(r"\1", text)
    return text


def _replace_piped_link(match: re.Match) -> str:
    target, label = match.group(1), match.group(2)
    return label.strip() if label.strip() else _readable_target(target)


def _replace_plain_link(match: re.Match) -> str:
    return _readable_target(match.group(1))


def _readable_target(raw_target: str) -> str:
    """''[[Cible]]'' -> texte lisible (retire section et préfixe namespace)."""
    target = raw_target.split("#", 1)[0]
    if ":" in target and not target.lower().startswith("mediawiki"):
        target = target.split(":", 1)[1]
    return target.strip()


# ---------------------------------------------------------------------------
# Indentation.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Dialogues / listes.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Divers.
# ---------------------------------------------------------------------------
def collapse_empty_galleries(markdown_text: str) -> str:
    """Supprime les balises ``<gallery>`` laissées par le pré-traitement."""
    return re.sub(r"(?i)<\s*gallery[^>]*>.*?<\s*/\s*gallery\s*>", "",
                  markdown_text, flags=re.DOTALL)


def strip_excess_blank_lines(markdown_text: str) -> str:
    """Réduit les suites de lignes vides à une seule et nettoie les espaces."""
    text = re.sub(r"\n{3,}", "\n\n", markdown_text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)
    return text