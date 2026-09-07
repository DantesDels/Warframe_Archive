"""Constantes du Warframe Public Export (index + serveur de contenu)."""

ORIGIN_BASE = "https://origin.warframe.com/PublicExport"
CONTENT_BASE = "http://content.warframe.com/PublicExport/Manifest"

DEFAULT_LANGS = ("en", "fr")

# Catégories d'entités retenues pour ``game_entities_i18n``.  Chaque clé est le
# préfixe du manifest ; la valeur est le libellé ``entity_type`` stocké en base.
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