"""Polissage final : galeries vides et lignes blanches en excès."""

from __future__ import annotations

import re


def collapse_empty_galleries(markdown_text: str) -> str:
    """Supprime les balises ``<gallery>`` laissées par le pré-traitement."""
    return re.sub(r"(?i)<\s*gallery[^>]*>.*?<\s*/\s*gallery\s*>", "",
                  markdown_text, flags=re.DOTALL)


def strip_excess_blank_lines(markdown_text: str) -> str:
    """Réduit les suites de lignes vides à une seule et nettoie les espaces."""
    text = re.sub(r"\n{3,}", "\n\n", markdown_text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)
    return text


__all__ = ["collapse_empty_galleries", "strip_excess_blank_lines"]