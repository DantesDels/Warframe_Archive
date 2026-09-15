"""Description of a logical output bucket."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CategorySpec:
    """Description of a logical output bucket.

    Attributes:
        id: unique bucket identifier (used for state tracking).
        title: human-readable label (becomes the ``category`` field of entries).
        filename: output megafile name (e.g. ``Lore_Quetes.json``).
        source: backend source name that owns this bucket (e.g.
            ``mediawiki-warframe``, ``warframe-com-fr``).
        categories: actual source category names to resolve.
        prefix: title prefixes to expand via ``list=allpages`` (source
            complementary to categories, useful when the wiki does not
            categorize all pages, e.g. ``Kinemantik Instant Messenger/``).
        title_include: keep only titles containing ANY of these substrings.
        title_exclude: exclude titles containing ANY of these substrings.
    """

    id: str
    title: str
    filename: str
    source: str = "mediawiki-warframe"
    categories: list[str] = field(default_factory=list)
    prefix: list[str] = field(default_factory=list)
    title_include: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)
