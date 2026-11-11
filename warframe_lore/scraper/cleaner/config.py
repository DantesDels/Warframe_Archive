"""Cleaning config: constants injected from ``cleaner_config.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Path to the cleaning config file (project root).
CLEANER_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "cleaner_config.json"
)


@dataclass
class CleanerConfig:
    """Cleaning constants loaded from ``cleaner_config.json``."""

    noise_substrings: tuple[str, ...] = ()
    noise_exact_names: frozenset[str] = frozenset()
    pure_noise: frozenset[str] = frozenset()
    audio: tuple[str, ...] = ()
    gameplay_exclude: tuple[str, ...] = ()
    lore_keep: tuple[str, ...] = ()
    non_canon_templates: frozenset[str] = frozenset()
    canon_templates: frozenset[str] = frozenset()
    marker_non_canon: str = "NON-CANON / SPECULATION JOUEUR"
    marker_canon: str = "CANON OFFICIEL"
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> CleanerConfig:
        src = path or CLEANER_CONFIG_PATH
        data = json.loads(src.read_text(encoding="utf-8"))
        t = data.get("templates", {})
        s = data.get("sections", {})
        sp = data.get("speculation", {})
        return cls(
            noise_substrings=tuple(t.get("noise_substrings", [])),
            noise_exact_names=frozenset(t.get("noise_exact_names", [])),
            pure_noise=frozenset(t.get("pure_noise", [])),
            audio=tuple(t.get("audio", [])),
            gameplay_exclude=tuple(s.get("gameplay_exclude", [])),
            lore_keep=tuple(s.get("lore_keep", [])),
            non_canon_templates=frozenset(sp.get("non_canon_templates", [])),
            canon_templates=frozenset(sp.get("canon_templates", [])),
            marker_non_canon=sp.get("marker_non_canon",
                                    "NON-CANON / SPECULATION JOUEUR"),
            marker_canon=sp.get("marker_canon", "CANON OFFICIEL"),
            raw=data,
        )


__all__ = ["CleanerConfig", "CLEANER_CONFIG_PATH"]
