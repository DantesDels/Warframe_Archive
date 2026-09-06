"""Orchestrateur du nettoyage : la classe :class:`WikitextCleaner`.

Coordonne les 5 sous-modules de la couche cleaner dans un ordre précis :
  1. preprocessing  -> assainissement du brut (commentaires, HTML, fichiers) ;
  2. parse          -> analyse structurelle (mwparserfromhell) ;
  3. templates      -> gestion des templates (bruit, quote, spoiler,
                       marqueurs canon/non-canon) ;
  4. formatting     -> liens, gras/italique, titres, dialogues ;
  5. sections       -> suppression des blocs gameplay.

La sortie est un objet :class:`CleanOutput` qui transporte, en plus du
Markdown, les signaux canon détectés *dans le corps* de la page
(speculation en ligne / confirmation en ligne).  Le statut canon au niveau
page (croisement avec ``Category:Speculation``) est calculé par
l'orchestrateur, pas ici.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import mwparserfromhell
from mwparserfromhell.nodes import Template

from . import CleanerConfig
from .formatting import (
    BULLET_TOKEN,
    collapse_empty_galleries,
    convert_markup_to_markdown,
    format_lists_and_dialogue,
    normalise_indentation,
    normalise_links,
    protect_bullets,
    reflow_headings_to_markdown,
    strip_excess_blank_lines,
)
from .preprocessing import (
    convert_html_tags,
    remove_transclusion_tags,
    strip_file_and_image_references,
    strip_tables_and_code_blocks,
    strip_wikitext_comments,
)
from .sections import drop_gameplay_sections
from .templates import (
    is_noise_template,
    is_pure_noise,
    must_flag_canon,
    must_flag_non_canon,
    render_canon_template,
    render_non_canon_template,
    render_quote_template,
    render_spoiler_template,
    strip_templates_to_text,
)


@dataclass
class CleanOutput:
    """Résultat du nettoyage d'une page.

    Attributes:
        markdown: texte final propre, prêt pour la sortie JSON.
        non_canon_detected_in_body: un template ``{{Speculation}}`` ou
            équivalent est apparu dans le corps de la page.
        canon_detected_in_body: un template de confirmation (``{{Canon}}``...)
            est apparu dans le corps de la page.
    """

    markdown: str
    non_canon_detected_in_body: bool = False
    canon_detected_in_body: bool = False


# Instructions de dialogue KIM (wiki) : liens d'enchaînement à supprimer du
# Markdown.  ``{Convo. ends.}`` est volontairement conservé (marqueur terminal
# consommé par le flow-chart du serveur).
# Instruction de navigation KIM en tête de ligne de dialogue (pointeurs wiki) :
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# et les variantes préfixées par une ou plusieurs conditions
# ``> **{If ...} {If ...} {Continues ...}`` ou ``> **> {...`` / ``> > {...``.
# Le mot-clé de navigation vit TOUJOURS dans une accolade ; la fermeture de
# l'accolade n'est pas exigée.  ``{If ...}`` et ``{Convo. ends.}`` ne
# contiennent pas ces mots-clés -> non concernés.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
# Pointeur de navigation embarqué (fermé) dans un message : retiré du texte,
# sauf si le contenu évoque un terminal ``{... ends ...}`` (ex: ``{Convo.
# Ends. Followed by jumpscare image.}``).
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_ARTIFACT_LINE = re.compile(r"^\s*>?\s*\*{1,2}\s*$")

# Noms de fichiers audio laissés par les lecteurs audio du Wiki dans les
# transcriptions de quêtes.  Deux formes observées dans les données :
#   * jeton unique        -> ``LeekterSlippery.ogg``, ``DCodexA00010Silvana_en.ogg``
#   * code créé en deux    -> ``DWraithQM1CrpArrive0060RJCephalon en.ogg``
#     morceaux (loc. en)     ``DThroneRoom0050Erra en.mp3`` ``BbPainAmbulas00020 en.ogg``
# Noter : ``[a-z0-9_]`` avec re.IGNORECASE accepte aussi les majuscules.
_AUDIO_LOCALE_TOKEN = re.compile(
    r"\b[a-z0-9_]+[ \t]{1,3}en\.(?:ogg|mp3)\b", re.IGNORECASE)
_AUDIO_FILE_TOKEN = re.compile(r"\b[\w-]+\.(?:ogg|mp3|wav)\b", re.IGNORECASE)


def _strip_audio_filenames(markdown: str) -> str:
    """Retire les métadonnées audio du Wiki (noms de fichiers .ogg/.mp3/.wav).

    Passe 1 : le code créé suivi de la locale est supprimé en un seul coup
    (``DThroneRoom0050Erra en.mp3``), sinon la locale ``en.ogg`` orpheline
    resterait collée au texte.
    Passe 2 : tout jeton autonome ``Word.ogg/.mp3/.wav`` restant.
    Passe 3 : les lignes devenues vides ou réduites à un seul locuteur
    (ex: ``> **Angel's song:**`` après suppression du fichier) sont retirées,
    d'où qu'elles viennent (escamotées par `_strip_audio_filenames`.
    """
    if not markdown:
        return markdown
    text = _AUDIO_LOCALE_TOKEN.sub("", markdown)
    text = _AUDIO_FILE_TOKEN.sub("", text)
    lines_out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        body = stripped[1:].strip() if stripped.startswith(">") else stripped
        # Locuteur résiduel seul sur sa ligne : ``> **Angel's song:**``
        body = re.sub(r"^\*\*[^*]*\*\*\s*:?\s*$", "", body)
        # Libellé résiduel seul : ``Angel's song:``
        body = re.sub(
            r"^[A-Za-z][\w'’]*(?:[ -][A-Za-z][\w'’]*)*\s*:\s*$", "", body)
        # Cruft Markdown (``*`` ``_`` ``>`` ``:`` ``"`` ``-`` …) sans texte.
        body = re.sub(r"[>*_:.\"'’\-\u2013\u2014]", "", body).strip()
        if body:
            lines_out.append(line)
    return "\n".join(lines_out)


def strip_kim_dialog_instructions(markdown: str) -> str:
    """Retire définitivement les instructions d'enchaînement KIM (``{...}``).

    Purgées : lignes-pointeurs de continuation, conditions de branche
    (``{If ...}``) et marqueurs de position (``{P1}`` …).  Elles ne doivent
    apparaître ni dans l'interface, ni dans les chunks du modèle RAG.
    """
    if not markdown:
        return markdown
    text = _KIM_POINTER_LINE.sub("", markdown)
    text = _KIM_INLINE_NAV.sub("", text)
    text = _KIM_CONDITION_MARK.sub("", text)
    text = _KIM_POSITION_MARK.sub("", text)
    text = _KIM_ARTIFACT_LINE.sub("", text)
    # Résidus de retrait d'un ``{If ...}`` entre ``> **`` et le nom :
    # ``> ** Arthur:**`` -> ``> **Arthur:**`` (ouverture seule, jamais la
    # paire de fermeture ``** texte``).
    text = re.sub(r"(?m)(^\s*[*>\-]+\s*)\*\*[ \t]+(?=\w)", r"\1**", text)
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    return text


# Nom de classe gardé pour compatibilité avec l'ancien module ``cleaner.py``.
class WikitextCleaner:
    """Convertit le Wikitext d'une page en Markdown propre pour LLM.

        Args:
            title: titre de la page (libellé humain, utilisé en debug).
            cleaner_config: constantes de nettoyage (injectées depuis
                ``config/cleaner_config.json``).
        """

    def __init__(self, title: str = "", cleaner_config: CleanerConfig | None = None) -> None:
        self.page_title = title or ""
        self.cleaner_config = cleaner_config or CleanerConfig.load()

    # ------------------------------------------------------------------ API
    def clean(self, wikitext: str) -> CleanOutput:
        """Nettoye le Wikitext et retourne le Markdown enrichi de signaux canon."""
        non_canon_detected = False
        canon_detected = False

        if not wikitext:
            return CleanOutput(markdown="")

        # Étape 1 — assainissement pré-parse (purges destructives).
        text = wikitext
        text = strip_wikitext_comments(text)
        text = strip_tables_and_code_blocks(text)
        text = convert_html_tags(text)
        text = remove_transclusion_tags(text)
        text = strip_file_and_image_references(text)
        parsed = mwparserfromhell.parse(text)

        # Étape 2 — gestion des templates d'intérêt narratif.
        # Détection canon/non-canon AVANT tout remplacement/aplatissement :
        # un template de signal peut être imbriqué dans un autre template ou
        # un nœud de liste ; filter_templates(recursive=True) le trouve alors
        # qu'une boucle sur parsed.nodes (surface) ne descend pas.
        all_templates = parsed.filter_templates(recursive=True)
        for node in all_templates:
            if must_flag_non_canon(node, self.cleaner_config):
                non_canon_detected = True
                continue
            if must_flag_canon(node, self.cleaner_config):
                canon_detected = True

        for node in list(parsed.nodes):
            if not isinstance(node, Template):
                continue
            template_name = str(node.name).strip().lower()

            if template_name == "quote":
                parsed.replace(node, render_quote_template(node))
            elif template_name == "spoiler":
                parsed.replace(node, render_spoiler_template(node))
            elif must_flag_non_canon(node, self.cleaner_config):
                parsed.replace(node, render_non_canon_template(node, self.cleaner_config))
            elif must_flag_canon(node, self.cleaner_config):
                parsed.replace(node, render_canon_template(node, self.cleaner_config))
            elif is_noise_template(template_name, self.cleaner_config) or \
                    is_pure_noise(template_name, self.cleaner_config):
                parsed.remove(node)

        text = str(parsed)

        # Étape 3 — templates résiduels -> premier argument pipe (fallback).
        text = strip_templates_to_text(text, self.cleaner_config)

        # Étape 4 — mise en forme Markdown.
        text = protect_bullets(text)
        text = convert_markup_to_markdown(text)
        text = normalise_links(text)
        text = drop_gameplay_sections(text, self.cleaner_config)
        text = reflow_headings_to_markdown(text)
        text = normalise_indentation(text)
        text = format_lists_and_dialogue(text)
        text = strip_kim_dialog_instructions(text)
        text = _strip_audio_filenames(text)
        text = collapse_empty_galleries(text)
        text = strip_excess_blank_lines(text)

        return CleanOutput(
            markdown=text.strip(),
            non_canon_detected_in_body=non_canon_detected,
            canon_detected_in_body=canon_detected,
        )


__all__ = ["CleanOutput", "WikitextCleaner", "BULLET_TOKEN"]