"""Guided crawl modes for universe capabilities (multi-universe presets)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CrawlModePreset:
    """Declarative budget preset with French guidance for the UI."""

    key: str
    label: str
    description: str
    max_pages: int | None = None
    max_depth: int | None = None
    max_manifest_urls: int | None = None
    source_timeout_seconds: int | None = None
    max_concurrency: int | None = None
    per_host_concurrency: int | None = None
    uses_tags: bool = False


CRAWL_MODES: tuple[CrawlModePreset, ...] = (
    CrawlModePreset(
        key="quick",
        label="Petite recherche (Aperçu rapide)",
        description=(
            "Idéal pour tester rapidement vos sources (30 pages/source, "
            "profondeur 1, timeout 2 min) et vérifier la qualité des extraits."
        ),
        max_pages=30, max_depth=1, max_manifest_urls=50,
        source_timeout_seconds=120, max_concurrency=4, per_host_concurrency=2,
    ),
    CrawlModePreset(
        key="thematic",
        label="Recherche thématique (par tags / catégories)",
        description=(
            "Cible uniquement un ou plusieurs thèmes via les tags ci-dessous "
            "(ex. Lore, Quests, Characters ou Jedi, Sith). Explore les "
            "catégories et articles correspondants sans bruit hors-sujet."
        ),
        max_pages=500, max_depth=3, max_manifest_urls=100,
        source_timeout_seconds=600, max_concurrency=4, per_host_concurrency=2,
        uses_tags=True,
    ),
    CrawlModePreset(
        key="global",
        label="Recherche globale (Synthèse de l'univers)",
        description=(
            "Couvre largement les portails, actualités, guides et articles "
            "majeurs de l'univers (1 000 pages/source, profondeur 3) pour une "
            "vue d'ensemble équilibrée."
        ),
        max_pages=1000, max_depth=3, max_manifest_urls=200,
        source_timeout_seconds=900, max_concurrency=6, per_host_concurrency=2,
    ),
    CrawlModePreset(
        key="exhaustive",
        label="Recherche poussée (Archive exhaustive)",
        description=(
            "Récupère absolument toutes les informations accessibles sur "
            "chaque source (jusqu'à 25 000 pages/source, profondeur 6, sans "
            "limite de temps par source — contrôlé via Pause / Annuler)."
        ),
        max_pages=25000, max_depth=6, max_manifest_urls=1000,
        source_timeout_seconds=0, max_concurrency=6, per_host_concurrency=3,
    ),
    CrawlModePreset(
        key="custom",
        label="Personnalisé",
        description=(
            "Réglages manuels libres de tous les paramètres et tags ci-dessous."
        ),
    ),
)

MODES_BY_KEY = {preset.key: preset for preset in CRAWL_MODES}


def parse_tags(raw: str | list[str] | tuple[str, ...]) -> list[str]:
    """Parse tag strings or lists into clean, case-insensitively unique tags."""
    joined = ",".join(str(x) for x in raw) if not isinstance(raw, str) else raw
    items = [part.strip() for part in joined.replace(";", ",").split(",")]
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique
