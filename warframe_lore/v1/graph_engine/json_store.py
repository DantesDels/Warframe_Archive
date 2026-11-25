"""JSON adapter for GraphStorePort, built on the shared atomic helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..scraper.storage import read_json, write_json
from .graph import KnowledgeGraph
from .models import ExtractedBatch
from .serialization import batch_from_dict, graph_from_dict, graph_to_dict


class JsonGraphStore:
    """Persist graph, Map cache and manifest as human-readable JSON files."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _extraction_path(self, chunk_id: str) -> Path:
        digest = hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()[:16]
        return self.root / "extracted" / f"{digest}.json"

    def load_graph(self) -> KnowledgeGraph:
        return graph_from_dict(read_json(self.root / "graph.json", {}))

    def save_graph(self, graph: KnowledgeGraph) -> None:
        write_json(self.root / "graph.json", graph_to_dict(graph))

    def load_manifest(self) -> dict[str, str]:
        raw = read_json(self.root / "manifest.json", {})
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    def save_manifest(self, manifest: dict[str, str]) -> None:
        write_json(self.root / "manifest.json", manifest)

    def load_extraction(self, chunk_id: str) -> ExtractedBatch | None:
        raw = read_json(self._extraction_path(chunk_id), None)
        return batch_from_dict(raw) if isinstance(raw, dict) else None

    def save_extraction(self, chunk_id: str, batch: ExtractedBatch) -> None:
        write_json(self._extraction_path(chunk_id), batch.to_dict())
