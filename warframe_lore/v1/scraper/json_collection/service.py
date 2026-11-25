"""Application service orchestrating discovery, manifest sync, filter and lookup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config_loader import load_preset
from .domain_pipeline import apply_dict_lookup, matches_collection_filter
from .http_adapter import HttpxJsonAdapter
from .manifest import ManifestStore
from .models import (
    CollectedJsonDocument,
    CollectionRunResult,
    JsonCollectionPreset,
)

_DEFAULT_LOGGER = logging.getLogger(__name__)


class JsonCollectionService:
    """Hexagonal use case driving generic JSON directory discovery and enrichment."""

    def __init__(
        self,
        adapter: HttpxJsonAdapter | None = None,
        manifest: ManifestStore | None = None,
        *,
        logger: Any = None,
    ) -> None:
        self.adapter = adapter or HttpxJsonAdapter()
        self.manifest = manifest or ManifestStore()
        self.logger = logger or _DEFAULT_LOGGER

    def run(
        self,
        preset: JsonCollectionPreset,
        *,
        force: bool = False,
        max_files: int | None = None,
    ) -> CollectionRunResult:
        """Execute discovery, incremental manifest check, filtering and dict_lookup."""
        result = CollectionRunResult()
        resources = self.adapter.discover_github_directory(preset.discovery)
        if max_files is not None and max_files > 0:
            resources = resources[:max_files]

        dictionaries: dict[str, dict[str, str]] = {}
        if preset.dict_lookup and preset.dict_lookup.dictionaries:
            for lang, url in preset.dict_lookup.dictionaries.items():
                try:
                    dictionaries[lang] = self.adapter.fetch_dictionary(
                        lang, url, self.manifest, force=force
                    )
                except Exception as exc:  # noqa: BLE001
                    msg = f"dict:{lang}:{url}: {exc}"
                    result.errors.append(msg)
                    self.logger.warning("Failed to load dictionary %s", msg)

        for res in resources:
            try:
                raw_data, unchanged, used_url = self.adapter.fetch_resource_json(
                    res, self.manifest, force=force
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{res.name}: {exc}")
                continue
            if unchanged:
                result.skipped_unchanged.append(res.name)
                continue
            accepted, _reason = matches_collection_filter(
                raw_data, preset.filter_rule
            )
            if not accepted:
                result.filtered_out.append(res.name)
                continue
            enriched, count, missing = apply_dict_lookup(
                raw_data,
                preset.dict_lookup,
                dictionaries,
                logger=self.logger,
            )
            result.missing_keys.extend(missing)
            result.documents.append(
                CollectedJsonDocument(
                    name=res.name,
                    source_url=used_url,
                    sha=res.sha,
                    data=enriched,
                    resolved_count=count,
                    missing_keys=missing,
                )
            )

        self.manifest.save()
        return result


def run_preset_collection(
    preset_path: Path | str,
    *,
    manifest_path: Path | str | None = None,
    force: bool = False,
    adapter: HttpxJsonAdapter | None = None,
    max_files: int | None = None,
) -> CollectionRunResult:
    """Convenience runner loading a preset file and executing the collection flow."""
    preset = load_preset(preset_path)
    store = ManifestStore(Path(manifest_path)) if manifest_path else ManifestStore()
    owns_adapter = adapter is None
    http_adapter = adapter or HttpxJsonAdapter()
    try:
        service = JsonCollectionService(adapter=http_adapter, manifest=store)
        return service.run(preset, force=force, max_files=max_files)
    finally:
        if owns_adapter:
            http_adapter.close()
