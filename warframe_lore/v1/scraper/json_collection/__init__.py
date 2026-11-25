"""Universal declarative GitHub/JSON collection, manifest sync and dict_lookup."""

from .config_loader import load_preset, load_preset_from_dict, parse_config_text
from .connector import GithubDirectoryConnector
from .domain_pipeline import (
    apply_dict_lookup,
    extract_collection_items,
    matches_collection_filter,
)
from .http_adapter import HttpxJsonAdapter
from .manifest import ManifestStore
from .models import (
    CollectedJsonDocument,
    CollectionFilterConfig,
    CollectionRunResult,
    DictLookupRuleConfig,
    DiscoveredResource,
    GithubDirectoryConfig,
    JsonCollectionPreset,
    ManifestEntry,
)
from .service import JsonCollectionService, run_preset_collection

__all__ = [
    "CollectedJsonDocument",
    "CollectionFilterConfig",
    "CollectionRunResult",
    "DictLookupRuleConfig",
    "DiscoveredResource",
    "GithubDirectoryConfig",
    "GithubDirectoryConnector",
    "HttpxJsonAdapter",
    "JsonCollectionPreset",
    "JsonCollectionService",
    "ManifestEntry",
    "ManifestStore",
    "apply_dict_lookup",
    "extract_collection_items",
    "load_preset",
    "load_preset_from_dict",
    "matches_collection_filter",
    "parse_config_text",
    "run_preset_collection",
]
