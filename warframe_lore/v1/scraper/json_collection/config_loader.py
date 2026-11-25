"""Declarative preset loader mapping parsed mappings to typed configs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_parser import parse_config_text
from .models import (
    CollectionFilterConfig,
    DictLookupRuleConfig,
    GithubDirectoryConfig,
    JsonCollectionPreset,
)


def load_preset_from_dict(raw: dict[str, Any]) -> JsonCollectionPreset:
    """Build a typed JsonCollectionPreset from a raw parsed mapping."""
    disc = dict(raw.get("discovery") or {})
    filt = dict(raw.get("filter") or raw.get("filters") or {})
    enrich = dict(raw.get("dict_lookup") or raw.get("enrichment") or {})

    discovery_cfg = GithubDirectoryConfig(
        repo=str(disc.get("repo") or ""),
        path=str(disc.get("path") or ""),
        ref=str(disc.get("ref") or "main"),
        pattern=str(disc.get("pattern") or disc.get("filter") or "*.json"),
        mirror_url_template=(
            str(disc["mirror_url_template"])
            if disc.get("mirror_url_template")
            else None
        ),
        token_env=str(disc.get("token_env") or "GITHUB_TOKEN"),
        api_base_url=str(disc.get("api_base_url") or "https://api.github.com"),
    )
    if not discovery_cfg.repo:
        raise ValueError("Preset discovery.repo is required")

    req_keys = filt.get("required_keys") or ()
    filter_cfg = CollectionFilterConfig(
        min_items=int(filt.get("min_items") or 0),
        max_items=int(filt["max_items"]) if filt.get("max_items") is not None else None,
        required_keys=tuple(str(k) for k in req_keys),
    )

    lookup_cfg: DictLookupRuleConfig | None = None
    if enrich and enrich.get("source_field"):
        dicts = {
            str(lang): str(url)
            for lang, url in dict(enrich.get("dictionaries") or {}).items()
        }
        lookup_cfg = DictLookupRuleConfig(
            source_field=str(enrich["source_field"]),
            target_field=str(enrich.get("target_field") or "resolved"),
            prefix=str(enrich["prefix"]) if enrich.get("prefix") else None,
            regex=str(enrich["regex"]) if enrich.get("regex") else None,
            dictionaries=dicts,
        )

    return JsonCollectionPreset(
        name=str(raw.get("name") or discovery_cfg.repo),
        discovery=discovery_cfg,
        filter_rule=filter_cfg,
        dict_lookup=lookup_cfg,
        metadata=dict(raw.get("metadata") or {}),
    )


def load_preset(path: Path | str) -> JsonCollectionPreset:
    """Load a declarative JSON or YAML collection preset from disk."""
    file_path = Path(path)
    if not file_path.is_file():
        v1_root = Path(__file__).resolve().parents[2]
        v1_candidate = v1_root / file_path
        if v1_candidate.is_file():
            file_path = v1_candidate
    raw = parse_config_text(file_path.read_text(encoding="utf-8"))
    return load_preset_from_dict(raw)
