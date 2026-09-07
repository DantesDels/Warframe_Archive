"""Constantes du pipeline média (Public Export officiel + miroir)."""

# Base des images content-addressed.
CONTENT_IMAGE_BASE = "https://content.warframe.com/PublicExport"

# Miroir maintenu automatiquement : reflète la publication officielle
# (ExportManifest n'est plus listé dans index_<lang>.txt.lzma depuis 2026).
MANIFEST_MIRROR_URL = (
    "https://raw.githubusercontent.com/calamity-inc/warframe-public-export/"
    "senpai/ExportManifest.json"
)

# Familles de manifests dont on extrait les noms publics (``name`` -> uid).
MANIFEST_FAMILIES = (
    "ExportCustoms", "ExportDrones", "ExportFlavour", "ExportFusionBundles",
    "ExportGear", "ExportKeys", "ExportRecipes", "ExportRegions",
    "ExportRelicArcane", "ExportResources", "ExportSentinels",
    "ExportSortieRewards", "ExportUpgrades", "ExportWarframes",
    "ExportWeapons",
)