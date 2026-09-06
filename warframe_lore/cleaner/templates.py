"""Gestion des templates MediaWiki pendant le nettoyage.

Deux familles de templates, deux traitements :
  * **Templates "bruit"** (infobox, navigation, maintenance) : suppression
    pure et simple.
  * **Templates porteurs de sens narrative** (Quote, Spoiler, Speculation,
    Canon) : convertis en blocs Markdown lisibles (blockquotes) avec des
    marqueurs explicites — notamment le marqueur **NON-CANON** qui signale
    la conjecture des joueurs (exigence de segmentation canon/non-canon).

Le nom anglais est volontairement ``NonCanon`` pour coller aux templates
réels du wiki (``{{Speculation}}``, ``{{Conjecture}}``).
"""

from __future__ import annotations

import re

import mwparserfromhell
from mwparserfromhell.nodes import Template

from . import CleanerConfig

# ---------------------------------------------------------------------------
# Template ``{{Quote|texte|personnage}}`` -> blockquote Markdown.
# ---------------------------------------------------------------------------
def render_quote_template(template_node: Template) -> str:
    """Convertit ``{{Quote|texte|personnage}}`` en blockquote Markdown."""
    params = [str(param.value).strip() for param in template_node.params]
    quote_text = params[0] if params else ""
    speaker_name = params[1] if len(params) > 1 else ""
    blockquote = f'\n> "{quote_text}"'
    if speaker_name and speaker_name.lower() != "in-game description":
        blockquote += f"\n> \u2014 {speaker_name}"
    return blockquote


# ---------------------------------------------------------------------------
# Template ``{{Spoiler|...}}`` -> blockquote marqueur.
# ---------------------------------------------------------------------------
def render_spoiler_template(template_node: Template) -> str:
    """Convertit ``{{Spoiler|texte}}`` en blockquote ``*_SPOILERS_*``."""
    params = [str(param.value).strip() for param in template_node.params]
    spoiler_hint = params[0] if params else "Spoiler"
    return f"\n> *_SPOILERS_* _: {spoiler_hint}_"


# ---------------------------------------------------------------------------
# Templates de statut canon (spéculation vs confirmation officielle).
# ---------------------------------------------------------------------------
def must_flag_non_canon(template_node: Template, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template marque la conjecture du joueur (ex: Speculation)."""
    return _template_name_matches(template_node, cleaner_config.non_canon_templates)


def must_flag_canon(template_node: Template, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template confirme le canon officiel (ex: Canon, Confirmed)."""
    return _template_name_matches(template_node, cleaner_config.canon_templates)


def _template_name_matches(template_node: Template, candidate_names) -> bool:
    template_name = str(template_node.name).strip().lower()
    return template_name in candidate_names


def render_non_canon_template(template_node: Template,
                              cleaner_config: CleanerConfig) -> str:
    """Rend le template de conjecture en marqueur NON-CANON explicite.

    Le premier argument pipe du template (ex: ``{{Speculation|...}}``)
    devient le texte du marqueur ; sinon marqueur générique.
    """
    params = [str(param.value).strip() for param in template_node.params]
    explanation_text = params[0] if params else ""
    marker_core = f"[{cleaner_config.marker_non_canon}]"
    if explanation_text:
        return f"\n> **{marker_core}** {explanation_text}\n"
    return f"\n> **{marker_core}**\n"


def render_canon_template(template_node: Template,
                          cleaner_config: CleanerConfig) -> str:
    """Rend le template de confirmation en marqueur CANON OFFICIEL."""
    params = [str(param.value).strip() for param in template_node.params]
    note_text = params[0] if params else ""
    marker_core = f"[{cleaner_config.marker_canon}]"
    if note_text:
        return f"\n> **{marker_core}** {note_text}\n"
    return f"\n> **{marker_core}**\n"


# ---------------------------------------------------------------------------
# Détection du bruit.
# ---------------------------------------------------------------------------
def is_noise_template(template_name: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template est dans les listes de bruit (infobox, nav, ...)."""
    normalized_name = template_name.strip().lower()
    if normalized_name in cleaner_config.noise_exact_names:
        return True
    return any(substring in normalized_name
               for substring in cleaner_config.noise_substrings)


def is_pure_noise(template_name: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template est un marqueur de maintenance sans valeur."""
    return template_name.strip().lower() in cleaner_config.pure_noise


# ---------------------------------------------------------------------------
# Suppression des templates restants (fallback équilibré).
# ---------------------------------------------------------------------------
_TEMPLATE_PATTERN = re.compile(r"\{\{((?:[^{}]|\{\{[^{}]*\}\})*)\}\}")


def strip_templates_to_text(wikitext: str,
                            cleaner_config: CleanerConfig) -> str:
    """Convertit les templates restants en leur premier argument pipe.

    Stratégie : si le template est du bruit -> rien ; sinon on garde le
    premier argument (texte affiché) ou le nom du template en fallback.
    """
    def _replace_template(match: re.Match) -> str:
        inner_body = match.group(1)
        template_name = inner_body.split("|", 1)[0].strip().lower()
        if is_noise_template(template_name, cleaner_config) or \
                is_pure_noise(template_name, cleaner_config):
            return ""
        if "|" in inner_body:
            first_piped_argument = inner_body.split("|", 1)[1]
            return first_piped_argument.strip()
        return template_name

    previous_text = None
    current_text = wikitext
    while previous_text != current_text:  # boucle jusqu'à point fixe (templates imbriqués)
        previous_text = current_text
        current_text = _TEMPLATE_PATTERN.sub(_replace_template, current_text)
    return current_text