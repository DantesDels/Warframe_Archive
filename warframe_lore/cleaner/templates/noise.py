"""Templates "bruit" : détection et suppression (fallback premier argument)."""

from __future__ import annotations

import re

from mwparserfromhell.nodes import Template

from warframe_lore.cleaner.config import CleanerConfig


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


__all__ = ["is_noise_template", "is_pure_noise", "strip_templates_to_text"]