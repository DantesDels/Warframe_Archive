"""Rendering of narrative templates (Quote, Spoiler, Speculation, Canon)."""

from __future__ import annotations

from mwparserfromhell.nodes import Template

from warframe_lore.cleaner.config import CleanerConfig


def render_quote_template(template_node: Template) -> str:
    """Converts ``{{Quote|text|speaker}}`` to a Markdown blockquote."""
    params = [str(param.value).strip() for param in template_node.params]
    quote_text = params[0] if params else ""
    speaker_name = params[1] if len(params) > 1 else ""
    blockquote = f'\n> "{quote_text}"'
    if speaker_name and speaker_name.lower() != "in-game description":
        blockquote += f"\n> \u2014 {speaker_name}"
    return blockquote


def render_spoiler_template(template_node: Template) -> str:
    """Converts ``{{Spoiler|text}}`` to a ``*_SPOILERS_*`` blockquote."""
    params = [str(param.value).strip() for param in template_node.params]
    spoiler_hint = params[0] if params else "Spoiler"
    return f"\n> *_SPOILERS_* _: {spoiler_hint}_"


def render_non_canon_template(template_node: Template,
                              cleaner_config: CleanerConfig) -> str:
    """Renders the speculation template as an explicit NON-CANON marker.

    The first pipe argument of the template (e.g. ``{{Speculation|...}}``)
    becomes the marker text; otherwise a generic marker is used.
    """
    params = [str(param.value).strip() for param in template_node.params]
    explanation_text = params[0] if params else ""
    marker_core = f"[{cleaner_config.marker_non_canon}]"
    if explanation_text:
        return f"\n> **{marker_core}** {explanation_text}\n"
    return f"\n> **{marker_core}**\n"


def render_canon_template(template_node: Template,
                          cleaner_config: CleanerConfig) -> str:
    """Renders the confirmation template as an OFFICIAL CANON marker."""
    params = [str(param.value).strip() for param in template_node.params]
    note_text = params[0] if params else ""
    marker_core = f"[{cleaner_config.marker_canon}]"
    if note_text:
        return f"\n> **{marker_core}** {note_text}\n"
    return f"\n> **{marker_core}**\n"


__all__ = [
    "render_quote_template",
    "render_spoiler_template",
    "render_non_canon_template",
    "render_canon_template",
]
