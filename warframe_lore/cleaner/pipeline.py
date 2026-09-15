"""Cleaning orchestrator: the :class:`WikitextCleaner` class.

Coordinates the cleaner sub-modules in a specific order:
  1. preprocessing/html+blocks -> raw sanitization (comments,
     HTML, files, tables, code);
  2. parse          -> structural analysis (mwparserfromhell);
  3. templates      -> template handling (noise, quote, spoiler,
                       canon/non-canon markers);
  4. formatting     -> links, bold/italic, headings, dialogue;
  5. audio/KIM      -> audio metadata and dialogue instructions;
  6. sections       -> gameplay block removal;
  7. polish         -> empty galleries and excess blank lines.

The output is a :class:`CleanOutput` object carrying, besides the
Markdown, canon signals detected *in the body* of the page
(inline speculation / inline confirmation).  The page-level canon
status (crossed with ``Category:Speculation``) is computed by the
orchestrator, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

import mwparserfromhell
from mwparserfromhell.nodes import Template

from warframe_lore.cleaner.audio import strip_audio_filenames
from warframe_lore.cleaner.blocks import (
    strip_file_and_image_references,
    strip_tables_and_code_blocks,
)
from warframe_lore.cleaner.bullets import BULLET_TOKEN, protect_bullets
from warframe_lore.cleaner.config import CleanerConfig
from warframe_lore.cleaner.dialogue_lines import (
    format_lists_and_dialogue,
    normalise_indentation,
)
from warframe_lore.cleaner.footers import cut_footer_noise
from warframe_lore.cleaner.headings import (
    normalise_deep_headings,
    reflow_headings_to_markdown,
)
from warframe_lore.cleaner.html import (
    convert_html_tags,
    remove_transclusion_tags,
    strip_wikitext_comments,
)
from warframe_lore.cleaner.kim_instructions import strip_kim_dialog_instructions
from warframe_lore.cleaner.links import normalise_links
from warframe_lore.cleaner.markup import convert_markup_to_markdown
from warframe_lore.cleaner.polish import (
    collapse_empty_galleries,
    strip_excess_blank_lines,
)
from warframe_lore.cleaner.sections import drop_gameplay_sections
from warframe_lore.cleaner.templates.noise import (
    is_noise_template,
    is_pure_noise,
    strip_templates_to_text,
)
from warframe_lore.cleaner.templates.render import (
    render_canon_template,
    render_non_canon_template,
    render_quote_template,
    render_spoiler_template,
)
from warframe_lore.cleaner.templates.signal import (
    must_flag_canon,
    must_flag_non_canon,
)


@dataclass
class CleanOutput:
    """Result of cleaning a page.

    Attributes:
        markdown: final clean text, ready for JSON output.
        non_canon_detected_in_body: a ``{{Speculation}}`` template or
            equivalent appeared in the page body.
        canon_detected_in_body: a confirmation template (``{{Canon}}``...)
            appeared in the page body.
    """

    markdown: str
    non_canon_detected_in_body: bool = False
    canon_detected_in_body: bool = False


# Class name kept for compatibility with the legacy ``cleaner.py`` module.
class WikitextCleaner:
    """Converts a page's Wikitext into clean Markdown for LLMs.

        Args:
            title: page title (human-readable label, used for debugging).
            cleaner_config: cleaning constants (injected from
                ``config/cleaner_config.json``).
        """

    def __init__(self, title: str = "",
                 cleaner_config: CleanerConfig | None = None) -> None:
        self.page_title = title or ""
        self.cleaner_config = cleaner_config or CleanerConfig.load()

    # ------------------------------------------------------------------ API
    def clean(self, wikitext: str) -> CleanOutput:
        """Cleans the Wikitext and returns Markdown enriched with canon signals."""
        non_canon_detected = False
        canon_detected = False

        if not wikitext:
            return CleanOutput(markdown="")

        # Step 1 -- pre-parse sanitization (destructive purges).
        text = wikitext
        text = strip_wikitext_comments(text)
        text = strip_tables_and_code_blocks(text)
        text = convert_html_tags(text)
        text = remove_transclusion_tags(text)
        text = strip_file_and_image_references(text)
        parsed = mwparserfromhell.parse(text)

        # Step 2 -- narrative-interest template handling.
        # Canon/non-canon detection BEFORE any replacement/flattening:
        # a signal template may be nested inside another template or
        # list node; filter_templates(recursive=True) finds it whereas
        # a surface-level loop over parsed.nodes does not descend.
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
                parsed.replace(
                    node, render_non_canon_template(node, self.cleaner_config))
            elif must_flag_canon(node, self.cleaner_config):
                parsed.replace(node, render_canon_template(node, self.cleaner_config))
            elif is_noise_template(template_name, self.cleaner_config) or \
                    is_pure_noise(template_name, self.cleaner_config):
                parsed.remove(node)

        text = str(parsed)

        # Step 3 -- residual templates -> first pipe argument (fallback).
        text = strip_templates_to_text(text, self.cleaner_config)

        # Step 4 -- Markdown formatting.
        text = protect_bullets(text)
        text = convert_markup_to_markdown(text)
        text = normalise_links(text)
        text = drop_gameplay_sections(text, self.cleaner_config)
        text = reflow_headings_to_markdown(text)
        text = normalise_deep_headings(text)
        text = normalise_indentation(text)
        text = format_lists_and_dialogue(text)
        text = strip_kim_dialog_instructions(text)
        text = cut_footer_noise(text)
        text = strip_audio_filenames(text)
        text = collapse_empty_galleries(text)
        text = strip_excess_blank_lines(text)

        return CleanOutput(
            markdown=text.strip(),
            non_canon_detected_in_body=non_canon_detected,
            canon_detected_in_body=canon_detected,
        )


__all__ = ["CleanOutput", "WikitextCleaner", "BULLET_TOKEN"]
