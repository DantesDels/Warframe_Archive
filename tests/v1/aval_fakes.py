"""Shared fakes and a generic mini-universe for downstream pipeline tests.

The mini-universe ("Chronicles of Aurelia") is fictional and generic:
two factions, two characters with aliases, one location and one event,
split across two narrative arcs connected by bridge relations.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from warframe_lore.v1.blueprint import Blueprint, blueprint_from_dict
from warframe_lore.v1.graph_engine.engine import GraphEngine
from warframe_lore.v1.graph_engine.graph import KnowledgeGraph
from warframe_lore.v1.graph_engine.json_store import JsonGraphStore
from warframe_lore.v1.scraper.ports.outbound.llm import LlmRequest, LlmResponse

BLUEPRINT_DICT: dict[str, Any] = {
    "name": "Test blueprint",
    "entity_types": {
        "character": {"label": "Characters", "folder": "01_Characters"},
        "faction": {"label": "Factions", "folder": "02_Factions"},
        "location": {"label": "Locations", "folder": "03_Locations"},
        "event": {"label": "Events", "folder": "04_Events"},
        "concept": {"label": "Concepts", "folder": "05_Concepts"},
    },
    "relation_types": {
        "BELONGS_TO": {"label": "member of"},
        "LOCATED_IN": {"label": "located in"},
        "ALLIED_WITH": {"label": "allied with"},
        "OPPOSES": {"label": "opposes"},
        "OCCURRED_IN": {"label": "occurred in"},
        "RELATED_TO": {"label": "related to"},
    },
    "sections": {
        "micro": {
            "identity": "Identity",
            "facts": "Established facts",
            "relations": "Relations",
            "sources": "Sources",
        },
        "meso": {
            "members": "Members",
            "interactions": "Internal interactions",
            "stakes": "Stakes",
            "sources": "Sources",
        },
        "macro": {
            "overview": "Overview",
            "balance": "Balance of power",
            "timeline": "Master timeline",
            "bridges": "Bridges between arcs",
        },
    },
    "styles": {
        "mermaid_direction": "LR",
        "canvas_node_width": 260,
        "canvas_node_height": 120,
        "canvas_columns": 4,
        "timeline_entity_type": "event",
    },
    "vault": {
        "arcs_folder": "06_Arcs",
        "macro_note": "00_Vue_Globale.md",
        "macro_title": "Global view",
        "root_index": "00_Index.md",
    },
}

LLM_RESPONSES: dict[str, str] = {
    "doc-a::0": json.dumps(
        {
            "entities": [
                {
                    "name": "Commander Valen",
                    "type": "character",
                    "aliases": ["Shadow Blade"],
                    "attributes": {"role": "commander"},
                    "facts": [
                        {
                            "statement": "Commander Valen leads the Iron Covenant.",
                            "source_id": "doc-a::0",
                            "arc": "Iron Rising",
                        }
                    ],
                },
                {
                    "name": "Iron Covenant",
                    "type": "faction",
                    "aliases": [],
                    "facts": [
                        {
                            "statement": "The Iron Covenant guards Sector Aurelia.",
                            "source_id": "doc-a::0",
                            "arc": "Iron Rising",
                        }
                    ],
                },
                {
                    "name": "Sector Aurelia",
                    "type": "location",
                    "aliases": [],
                    "facts": [],
                },
            ],
            "relations": [
                {
                    "source": "Commander Valen",
                    "target": "Iron Covenant",
                    "type": "BELONGS_TO",
                    "arc": "Iron Rising",
                    "evolution": "",
                    "source_id": "doc-a::0",
                },
                {
                    "source": "Iron Covenant",
                    "target": "Sector Aurelia",
                    "type": "LOCATED_IN",
                    "arc": "Iron Rising",
                    "evolution": "",
                    "source_id": "doc-a::0",
                },
            ],
        }
    ),
    "doc-a::1": json.dumps(
        {
            "entities": [
                {
                    "name": "Lyra",
                    "type": "character",
                    "aliases": ["Dawn Singer"],
                    "facts": [
                        {
                            "statement": "Lyra opposes the Iron Covenant.",
                            "source_id": "doc-a::1",
                            "arc": "Siege of Aurelia",
                        }
                    ],
                }
            ],
            "relations": [
                {
                    "source": "Lyra",
                    "target": "Iron Covenant",
                    "type": "OPPOSES",
                    "arc": "Siege of Aurelia",
                    "evolution": "former ally turned enemy after the siege",
                    "source_id": "doc-a::1",
                }
            ],
        }
    ),
    "doc-b::0": json.dumps(
        {
            "entities": [
                {
                    "name": "Crimson Syndicate",
                    "type": "faction",
                    "aliases": [],
                    "facts": [],
                },
                {
                    "name": "Siege of Aurelia",
                    "type": "event",
                    "aliases": [],
                    "facts": [
                        {
                            "statement": "The siege ended with a broken alliance.",
                            "source_id": "doc-b::0",
                            "arc": "Siege of Aurelia",
                        }
                    ],
                },
            ],
            "relations": [
                {
                    "source": "Crimson Syndicate",
                    "target": "Lyra",
                    "type": "ALLIED_WITH",
                    "arc": "Siege of Aurelia",
                    "evolution": "",
                    "source_id": "doc-b::0",
                },
                {
                    "source": "Siege of Aurelia",
                    "target": "Sector Aurelia",
                    "type": "OCCURRED_IN",
                    "arc": "Siege of Aurelia",
                    "evolution": "",
                    "source_id": "doc-b::0",
                },
            ],
        }
    ),
}

MINI_CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "doc-a::0",
        "universe_id": "aurelia",
        "source_id": "src-a",
        "url": "https://example.org/lore/valen",
        "version": 1,
        "trust_score": 1.0,
        "timestamp": None,
        "chunk_index": 0,
        "text": (
            "Commander Valen (alias Shadow Blade) belongs to the Iron Covenant. "
            "The Iron Covenant guards Sector Aurelia."
        ),
    },
    {
        "chunk_id": "doc-a::1",
        "universe_id": "aurelia",
        "source_id": "src-a",
        "url": "https://example.org/lore/lyra",
        "version": 1,
        "trust_score": 0.7,
        "timestamp": None,
        "chunk_index": 1,
        "text": (
            "Lyra, known as Dawn Singer, opposes the Iron Covenant "
            "during the Siege of Aurelia."
        ),
    },
    {
        "chunk_id": "doc-b::0",
        "universe_id": "aurelia",
        "source_id": "src-b",
        "url": "https://example.org/lore/siege",
        "version": 1,
        "trust_score": 0.7,
        "timestamp": None,
        "chunk_index": 0,
        "text": (
            "The Crimson Syndicate allied with Lyra. "
            "The Siege of Aurelia occurred in Sector Aurelia."
        ),
    },
]


def make_blueprint() -> Blueprint:
    """Return the generic test blueprint."""
    return blueprint_from_dict(BLUEPRINT_DICT)


class FakeLlm:
    """Scripted LlmPort fake: one canned JSON answer per chunk id."""

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        fail_chunks: set[str] | None = None,
    ) -> None:
        self.responses = responses if responses is not None else dict(LLM_RESPONSES)
        self.fail_chunks = fail_chunks or set()
        self.calls: list[str] = []

    def generate(self, request: LlmRequest) -> LlmResponse:
        chunk_ids = re.findall(r"\[CHUNK ([^\]]+)\]", request.prompt)
        self.calls.extend(chunk_ids)
        for chunk_id in chunk_ids:
            if chunk_id in self.fail_chunks:
                raise RuntimeError("LLM budget reached")
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        for chunk_id in chunk_ids:
            data = json.loads(self.responses.get(chunk_id, "{}"))
            entities.extend(data.get("entities") or [])
            relations.extend(data.get("relations") or [])
        return LlmResponse(
            text=json.dumps({"entities": entities, "relations": relations}),
            tokens_used=10,
            model="fake",
        )


def write_export(
    root: Path,
    chunks: list[dict[str, Any]] | None = None,
) -> Path:
    """Write a minimal Scraper v1 run export (chunks, documents, manifest)."""
    chunks = MINI_CHUNKS if chunks is None else chunks
    root.mkdir(parents=True, exist_ok=True)
    chunks_path = root / "chunks.jsonl"
    chunks_path.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks),
        encoding="utf-8",
    )
    docs = [
        {
            "id": chunk["chunk_id"].split("::")[0],
            "universeId": chunk["universe_id"],
            "sourceId": chunk["source_id"],
            "title": f"Document {chunk['chunk_id'].split('::')[0]}",
            "url": chunk["url"],
            "docType": "website",
            "language": "en",
            "relevance": 1.0,
            "version": 1,
        }
        for chunk in chunks
    ]
    (root / "documents.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in docs), encoding="utf-8"
    )
    manifest = {
        "schema_version": "1.1",
        "universe": {"id": "aurelia", "name": "Chronicles of Aurelia"},
        "document_count": len(docs),
        "files": [
            {
                "name": "chunks.jsonl",
                "sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
                "bytes": chunks_path.stat().st_size,
            }
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return root


def run_engine(
    tmp_path: Path, llm: FakeLlm | None = None, batch_size: int = 1
) -> tuple[KnowledgeGraph, JsonGraphStore]:
    """Run the engine on the mini-universe export and return graph + store."""
    export_dir = write_export(tmp_path / "export")
    store = JsonGraphStore(tmp_path / "store")
    engine = GraphEngine(
        make_blueprint(), llm or FakeLlm(), store, batch_size=batch_size
    )
    return engine.run(export_dir), store
