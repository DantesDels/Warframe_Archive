"""SourceConnectorPort adapter integrating github_directory into Scraper v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ports.outbound.sources import CollectedPage, ConnectorContext
from .config_loader import load_preset, load_preset_from_dict
from .http_adapter import HttpxJsonAdapter
from .manifest import ManifestStore
from .models import JsonCollectionPreset
from .service import JsonCollectionService


class GithubDirectoryConnector:
    """Connector bridging declarative github_directory sources into CollectedPage."""

    name = "github_directory"
    kinds = ("github_directory", "json_preset")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        kind = str(source.get("kind", "")).lower()
        loc = str(source.get("location", "")).lower()
        return kind in self.kinds or loc.endswith((".preset.yaml", ".preset.json"))

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        preset = self._resolve_preset(source)
        force = bool(
            source.get("force")
            or ctx.limits.get("force")
            or not ctx.limits.get("incremental", True)
        )
        manifest_file = source.get("manifest_path") or ctx.limits.get("manifest_path")
        store = (
            ManifestStore(Path(str(manifest_file)))
            if manifest_file
            else ManifestStore()
        )
        max_pages = int(ctx.limits.get("max_pages_per_source", 200))
        adapter = HttpxJsonAdapter()
        try:
            service = JsonCollectionService(adapter=adapter, manifest=store)
            run_res = service.run(preset, force=force, max_files=max_pages)
        finally:
            adapter.close()

        pages: list[CollectedPage] = []
        for doc in run_res.documents:
            serialized = json.dumps(doc.data, ensure_ascii=False, indent=2)
            pages.append(
                CollectedPage(
                    title=doc.name,
                    url=doc.source_url,
                    content=serialized,
                    content_type="application/json",
                    metadata={
                        "connector": self.name,
                        "sha": doc.sha,
                        "resolved_count": doc.resolved_count,
                        "missing_keys": list(doc.missing_keys),
                        **preset.metadata,
                    },
                )
            )
        return pages

    @staticmethod
    def _resolve_preset(source: dict[str, Any]) -> JsonCollectionPreset:
        preset_path = source.get("preset_path") or source.get("location")
        if isinstance(preset_path, (str, Path)) and Path(str(preset_path)).is_file():
            return load_preset(Path(str(preset_path)))
        if "discovery" in source:
            return load_preset_from_dict(source)
        return load_preset_from_dict(
            {
                "name": str(source.get("title") or source.get("repo") or "github_dir"),
                "discovery": {
                    "repo": str(source.get("repo") or source.get("location") or ""),
                    "path": str(source.get("path") or ""),
                    "ref": str(source.get("ref") or "main"),
                    "pattern": str(source.get("pattern") or "*.json"),
                    "mirror_url_template": source.get("mirror_url_template"),
                },
                "filter": dict(source.get("filter") or {}),
                "dict_lookup": dict(source.get("dict_lookup") or {}),
            }
        )
