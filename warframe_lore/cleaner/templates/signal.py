"""Détection des templates de signal canon/non-canon."""

from __future__ import annotations

from mwparserfromhell.nodes import Template

from warframe_lore.cleaner.config import CleanerConfig


def must_flag_non_canon(template_node: Template, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template marque la conjecture du joueur (ex: Speculation)."""
    return _template_name_matches(template_node, cleaner_config.non_canon_templates)


def must_flag_canon(template_node: Template, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le template confirme le canon officiel (ex: Canon, Confirmed)."""
    return _template_name_matches(template_node, cleaner_config.canon_templates)


def _template_name_matches(template_node: Template, candidate_names) -> bool:
    template_name = str(template_node.name).strip().lower()
    return template_name in candidate_names


__all__ = ["must_flag_non_canon", "must_flag_canon"]