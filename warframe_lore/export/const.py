"""Warframe Public Export constants (index + content server)."""

ORIGIN_BASE = "https://origin.warframe.com/PublicExport"
CONTENT_BASE = "http://content.warframe.com/PublicExport/Manifest"

DEFAULT_LANGS = ("en", "fr")

# Entity categories selected for ``game_entities_i18n``.  Each key is the
# manifest prefix; the value is the ``entity_type`` label stored in the database.
EXPORT_CATEGORIES: dict[str, str] = {
    "ExportCustoms": "Customs",
    "ExportGear": "Gear",
    "ExportKeys": "Keys",
    "ExportRecipes": "Recipes",
    "ExportRegions": "Regions",
    "ExportRelicArcane": "RelicArcane",
    "ExportResources": "Resources",
    "ExportUpgrades": "Upgrades",
    "ExportWarframes": "Warframes",
    "ExportWeapons": "Weapons",
}
