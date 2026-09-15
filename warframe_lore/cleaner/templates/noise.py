"""Noise templates: detection and removal (first-argument fallback)."""

from __future__ import annotations

import re

from warframe_lore.cleaner.config import CleanerConfig


def is_noise_template(template_name: str, cleaner_config: CleanerConfig) -> bool:
    """True if the template is in the noise lists (infobox, nav, ...)."""
    normalized_name = template_name.strip().lower()
    if normalized_name in cleaner_config.noise_exact_names:
        return True
    return any(substring in normalized_name
               for substring in cleaner_config.noise_substrings)


def is_pure_noise(template_name: str, cleaner_config: CleanerConfig) -> bool:
    """True if the template is a valueless maintenance marker."""
    return template_name.strip().lower() in cleaner_config.pure_noise


_TEMPLATE_PATTERN = re.compile(r"\{\{((?:[^{}]|\{\{[^{}]*\}\})*)\}\}")


def strip_templates_to_text(wikitext: str,
                            cleaner_config: CleanerConfig) -> str:
    """Converts remaining templates to their first pipe argument.

    Strategy: if the template is noise -> nothing; otherwise keep the
    first argument (displayed text) or the template name as fallback.
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
    while previous_text != current_text:  # loop until fixed point (nested templates)
        previous_text = current_text
        current_text = _TEMPLATE_PATTERN.sub(_replace_template, current_text)
    return current_text


__all__ = ["is_noise_template", "is_pure_noise", "strip_templates_to_text"]
