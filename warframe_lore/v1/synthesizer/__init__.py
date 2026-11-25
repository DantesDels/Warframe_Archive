"""Stage 3: hierarchical Obsidian vault synthesis from the knowledge graph."""

from __future__ import annotations

from .autolink import autolink
from .canvas import community_canvas, macro_canvas
from .frontmatter import parse_frontmatter, render_frontmatter
from .manifest import content_hash, is_locked
from .mermaid import entity_mermaid
from .notes_macro import render_macro_note
from .notes_meso import render_community_note
from .notes_micro import render_entity_note
from .ports import VaultExporterPort
from .synthesizer import ObsidianSynthesizer, SynthesisReport
from .vault import ObsidianVaultExporter

__all__ = [
    "ObsidianSynthesizer",
    "ObsidianVaultExporter",
    "SynthesisReport",
    "VaultExporterPort",
    "autolink",
    "community_canvas",
    "content_hash",
    "entity_mermaid",
    "is_locked",
    "macro_canvas",
    "parse_frontmatter",
    "render_community_note",
    "render_entity_note",
    "render_frontmatter",
    "render_macro_note",
]
