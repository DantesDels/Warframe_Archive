"""Constants for the media pipeline (official Public Export + mirror)."""

# Content-addressed image base.
CONTENT_IMAGE_BASE = "https://content.warframe.com/PublicExport"

# Automatically maintained mirror: reflects the official release
# (ExportManifest is no longer listed in index_<lang>.txt.lzma since 2026).
MANIFEST_MIRROR_URL = (
    "https://raw.githubusercontent.com/calamity-inc/warframe-public-export/"
    "senpai/ExportManifest.json"
)

# Manifest families from which public names are extracted (``name`` -> uid).
MANIFEST_FAMILIES = (
    "ExportCustoms", "ExportDrones", "ExportFlavour", "ExportFusionBundles",
    "ExportGear", "ExportKeys", "ExportRecipes", "ExportRegions",
    "ExportRelicArcane", "ExportResources", "ExportSentinels",
    "ExportSortieRewards", "ExportUpgrades", "ExportWarframes",
    "ExportWeapons",
)
