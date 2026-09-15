"""Structured extraction of the warframe directory pages.

Warframe pages embed the official French blurb right after the label line
(``Warframe: Ash``, ``Ash``, <blurb>, ``Ash Prime``, <blurb>): a page yields
base and/or Prime rows, deduplicated later on ``(frame_name, is_prime)``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WarframeRow:
    """A warframe directory row (base or Prime variant)."""

    frame_name: str
    is_prime: bool
    description: str | None
    source_url: str | None


def parse_warframe_page(
    markdown: str, page_title: str, source_url: str | None
) -> list[WarframeRow]:
    """Parses one warframe page into base and/or Prime rows.

    Both blurbs live on the base page, so a base page emits two rows; the
    Prime-only page duplicates them and is skipped by the name-level
    deduplication of the pipeline.
    """
    lines = [line.strip() for line in markdown.split("\n") if line.strip()]
    if not lines:
        return []
    display_name = lines[0].split(":", 1)[1].strip()
    base_name = display_name.removesuffix(" Prime")
    # On a Prime-only page the display name is already 'X Prime': do not
    # append the suffix twice ('Ash Prime Prime').
    prime_label = (
        display_name if display_name.endswith(" Prime") else display_name + " Prime"
    )
    rows: list[WarframeRow] = []
    is_prime_page = page_title.rsplit("/", 1)[-1].endswith("-prime")
    if not is_prime_page:
        rows.append(
            WarframeRow(
                base_name,
                False,
                _description_after_label(lines, base_name),
                source_url,
            )
        )
    prime_desc = _description_after_label(lines, prime_label)
    if prime_desc is not None:
        rows.append(WarframeRow(base_name, True, prime_desc, source_url))
    return rows


def _description_after_label(lines: list[str], label: str) -> str | None:
    """Blurb right after the first exact ``label`` occurrence.

    The page opens with ``Warframe: X``, the ``X`` name label and its blurb;
    later occurrences of ``X`` are ability headers that must be ignored.
    """
    indexes = [i for i, line in enumerate(lines) if line == label]
    if not indexes:
        return None
    desc_index = indexes[0] + 1
    if desc_index >= len(lines):
        return None
    description = lines[desc_index]
    if len(description) < 15 or description.isupper():
        return None
    return description
