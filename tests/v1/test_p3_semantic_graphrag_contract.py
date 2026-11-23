"""Contract tests for Phase P3: semantic extraction, LLM budgets & GraphRAG."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from warframe_lore.v1.scraper.adapters.outbound.llm.openai_compat import (
    OpenAiCompatLlmAdapter,
)
from warframe_lore.v1.scraper.capabilities.models import LlmBudget
from warframe_lore.v1.scraper.ports.outbound.llm import LlmRequest
from warframe_lore.v1.scraper.semantic import (
    Entity,
    Mention,
    Relation,
    doc_taxonomy,
    enrich_chunk_with_llm,
    export_graphrag_bundle,
    extract_chunk_rules,
    extract_universe_semantics,
    resolve_aliases,
    semantic_to_graph_dict,
)
from warframe_lore.v1.scraper.UI.artifacts import emit_artifacts
from warframe_lore.v1.scraper.UI.workspace import WorkshopWorkspace


def test_rule_extraction_fr_and_en_entities_timelines_aliases_relations() -> None:
    text = (
        "Commander Valen (alias Shadow Blade) belongs to the Iron Covenant. "
        "The Iron Covenant opposes the Crimson Syndicate in Sector Aurelia "
        "during Era 2450."
    )
    entities, relations, mentions = extract_chunk_rules(
        text,
        doc_id="doc-1",
        chunk_id="doc-1::0",
        url="https://example.org/lore/valen",
        doc_title="Commander Valen",
        taxonomy=["chronicle", "faction"],
    )
    by_name = {e.name: e for e in entities}
    assert "Commander Valen" in by_name
    assert "Shadow Blade" in by_name["Commander Valen"].aliases
    assert any(e.kind == "timeline" and "2450" in e.name for e in entities)
    assert any(e.kind == "faction" for e in entities)
    rel_types = {r.relation_type for r in relations}
    assert "BELONGS_TO" in rel_types or "OPPOSES" in rel_types
    assert all(m.chunk_id == "doc-1::0" for m in mentions)

    tax = doc_taxonomy({"category": "Lore", "docType": "article"}, "Histoire")
    assert tax == ["Lore", "article", "Histoire"]


def test_openai_compat_adapter_enforces_enabled_calls_and_token_budgets() -> None:
    disabled = OpenAiCompatLlmAdapter(LlmBudget(enabled=False, model="local-7b"))
    with pytest.raises(RuntimeError, match="désactivé"):
        disabled.generate(LlmRequest(prompt="hello", max_tokens=64))

    noop = OpenAiCompatLlmAdapter(LlmBudget(enabled=True, model=""))
    empty_resp = noop.generate(LlmRequest(prompt="hello", max_tokens=64))
    assert empty_resp.text == ""
    assert noop.calls == 0

    calls_seen: list[dict[str, Any]] = []

    class FakeResp:
        status_code = 200

        def __init__(self, body: dict[str, Any]) -> None:
            self._body = body

        def json(self) -> dict[str, Any]:
            return self._body

    class FakeHttp:
        def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: Any,
        ) -> FakeResp:
            calls_seen.append({"url": url, "payload": json, "headers": headers})
            return FakeResp(
                {
                    "choices": [
                        {"message": {"content": '{"entities":[],"relations":[]}'}}
                    ],
                    "usage": {"total_tokens": 120},
                }
            )

    budget = LlmBudget(
        enabled=True,
        model="demo-llm",
        endpoint="http://127.0.0.1:1234/v1",
        max_tokens=200,
        max_calls=2,
        vram_gb=8.0,
    )
    adapter = OpenAiCompatLlmAdapter(budget, api_key="secret", http_client=FakeHttp())
    r1 = adapter.generate(LlmRequest(prompt="Extract", max_tokens=150))
    assert r1.tokens_used == 120
    assert adapter.remaining_calls() == 1
    assert adapter.remaining_tokens() == 80
    assert calls_seen[0]["url"].endswith("/chat/completions")
    assert calls_seen[0]["headers"]["Authorization"] == "Bearer secret"

    # Second call clamps max_tokens to remaining 80, uses 120 -> total 240 >= 200
    adapter.generate(LlmRequest(prompt="Extract 2", max_tokens=500))
    assert calls_seen[1]["payload"]["max_tokens"] == 80

    with pytest.raises(RuntimeError, match="Budget LLM"):
        adapter.generate(LlmRequest(prompt="Extract 3", max_tokens=64))


def test_enrich_chunk_with_llm_parses_fenced_json_and_provenance() -> None:
    fenced = (
        "```json\n"
        '{"entities": ['
        '{"name": "Archivist Mira", "kind": "person", "aliases": ["Mira"]},'
        '{"name": "Obsidian Spire", "kind": "location"}'
        '], "relations": ['
        '{"source": "Archivist Mira", "target": "Obsidian Spire", '
        '"type": "LOCATED_IN", "evidence": "Mira dwells in Obsidian Spire"}'
        "]}\n```"
    )

    class FakeResp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "choices": [{"message": {"content": fenced}}],
                "usage": {"total_tokens": 90},
            }

    class FakeHttp:
        def post(self, *_args: Any, **_kwargs: Any) -> FakeResp:
            return FakeResp()

    adapter = OpenAiCompatLlmAdapter(
        LlmBudget(enabled=True, model="mock-llm", max_tokens=1000, max_calls=5),
        http_client=FakeHttp(),
    )
    entities, relations, mentions = enrich_chunk_with_llm(
        adapter,
        "Mira dwells in the Obsidian Spire.",
        doc_id="doc-9",
        chunk_id="doc-9::2",
        url="https://example.org/mira",
        taxonomy=["bio"],
    )
    assert len(entities) == 2
    assert all(e.extractor == "llm" for e in entities)
    assert len(relations) == 1
    assert relations[0].relation_type == "LOCATED_IN"
    assert relations[0].chunk_id == "doc-9::2"
    assert len(mentions) == 2


def test_resolve_aliases_merges_variants_and_remaps_relations_and_mentions() -> None:
    e1 = Entity(
        id="ent-1", name="Solaris Guild", kind="faction", aliases=["The Solaris"],
        chunk_ids=["d1::0"], document_ids=["d1"], mention_count=3, extractor="rules",
    )
    e2 = Entity(
        id="ent-2", name="The Solaris", kind="faction", aliases=["Solaris Guilds"],
        chunk_ids=["d2::1"], document_ids=["d2"], mention_count=1, extractor="llm",
    )
    e3 = Entity(
        id="ent-3", name="Citadel Veridia", kind="location",
        chunk_ids=["d1::0"], document_ids=["d1"], mention_count=2, extractor="rules",
    )
    rels = [
        Relation("r1", "ent-2", "ent-3", "LOCATED_IN", chunk_id="d2::1"),
        Relation("r2", "ent-1", "ent-2", "RELATED_TO", chunk_id="d1::0"),  # self-loop
    ]
    mens = [
        Mention("m1", "ent-2", "The Solaris", "d2", "d2::1"),
        Mention("m2", "ent-3", "Citadel Veridia", "d1", "d1::0"),
    ]
    merged, clean_rels, clean_mens = resolve_aliases([e1, e2, e3], rels, mens)
    assert len(merged) == 2
    guild = next(e for e in merged if e.name == "Solaris Guild")
    assert guild.mention_count == 4
    assert guild.extractor == "hybrid"
    assert "d1::0" in guild.chunk_ids and "d2::1" in guild.chunk_ids
    assert len(clean_rels) == 1
    assert clean_rels[0].source_id == guild.id
    assert clean_rels[0].target_id == "ent-3"
    assert any(m.entity_id == guild.id and m.chunk_id == "d2::1" for m in clean_mens)


def test_pipeline_hydrates_blobs_and_exports_graphrag_bundle(tmp_path: Path) -> None:
    ws = WorkshopWorkspace(path=tmp_path / "workspace.json")
    uni = ws.create("Chroniques Stellaires")
    uid = uni["id"]
    blob_dir = tmp_path / "blobs"
    blob_dir.mkdir(parents=True)
    full_body = (
        "Captain Lyra belongs to the Starlight Order. "
        "The Starlight Order is located in Citadel Helios during Era 3020."
    )
    (blob_dir / "doc_full.txt").write_text(full_body, encoding="utf-8")
    ws.data["documents"].append(
        {
            "id": "doc-42",
            "universeId": uid,
            "title": "Captain Lyra",
            "url": "https://example.org/lyra",
            "category": "characters",
            "docType": "lore",
            "content": "Captain Lyra...",
            "blobRef": "doc_full.txt",
        }
    )
    ws.save()

    bundle = extract_universe_semantics(ws, uid)
    assert bundle.stats["document_count"] == 1
    assert bundle.stats["chunk_count"] >= 1
    assert any("Starlight Order" in e.name for e in bundle.entities)
    assert any("doc-42::0" in e.chunk_ids for e in bundle.entities)
    assert uid in ws.data["knowledge_graphs"]

    out = tmp_path / "exports" / uid / "graphrag"
    paths = export_graphrag_bundle(out, uni, bundle)
    names = {p.name for p in paths}
    assert names == {
        "entities.jsonl",
        "relations.jsonl",
        "mentions.jsonl",
        "graphrag_bundle.json",
        "knowledge_graph.json",
        "knowledge_graph.html",
    }
    bundle_json = json.loads((out / "graphrag_bundle.json").read_text(encoding="utf-8"))
    assert bundle_json["chunk_links"]
    html = (out / "knowledge_graph.html").read_text(encoding="utf-8")
    assert "Personnages" in html and "Chronologie" in html

    # Opt-in emit_artifacts wiring
    run_out_off = tmp_path / "run_off"
    manifest_off = emit_artifacts(run_out_off, uni, ws.data["documents"], ["json"])
    assert not any(f["name"] == "graphrag_bundle.json" for f in manifest_off["files"])

    run_out_on = tmp_path / "run_on"
    manifest_on = emit_artifacts(
        run_out_on,
        uni,
        ws.data["documents"],
        ["json"],
        graph_rag_config={"enabled": True, "model": ""},
    )
    assert any(f["name"] == "graphrag_bundle.json" for f in manifest_on["files"])
    assert (run_out_on / "graphrag" / "entities.jsonl").is_file()


def test_ui_capabilities_llm_budget_and_graph_canvas_semantic_mode(
    tmp_path: Path,
) -> None:
    from PySide6.QtWidgets import QApplication

    from warframe_lore.v1.scraper.UI.dialogs.capabilities_dialog import (
        CapabilitiesDialog,
    )
    from warframe_lore.v1.scraper.UI.graph.view import GraphCanvas

    app = QApplication.instance() or QApplication([])
    assert app is not None

    dlg = CapabilitiesDialog(None, {})
    assert not dlg.llm_budget_box.isEnabled()
    dlg._toggles["graph_rag"].setChecked(True)
    assert dlg.llm_budget_box.isEnabled()
    dlg.llm_budget_box.endpoint_input.setText("http://127.0.0.1:8080/v1")
    dlg.llm_budget_box.model_input.setText("qwen2.5-7b")
    dlg.llm_budget_box.max_tokens_spin.setValue(4096)
    dlg.llm_budget_box.max_calls_spin.setValue(12)
    dlg.llm_budget_box.vram_spin.setValue(6.5)
    dlg._save()
    saved = dlg.result_capabilities
    assert saved is not None
    assert saved["graph_rag"]["enabled"] is True
    assert saved["graph_rag"]["endpoint"] == "http://127.0.0.1:8080/v1"
    assert saved["graph_rag"]["model"] == "qwen2.5-7b"
    assert saved["graph_rag"]["max_tokens"] == 4096
    assert saved["graph_rag"]["max_calls"] == 12
    assert saved["graph_rag"]["vram_gb"] == 6.5

    ws = WorkshopWorkspace(path=tmp_path / "ws_ui.json")
    uni = ws.create("Nebula")
    ws.data["documents"].append(
        {
            "id": "doc-u1",
            "universeId": uni["id"],
            "title": "High Council",
            "url": "https://example.org/council",
            "content": "High Council opposes Iron Fleet in Sector Nova.",
        }
    )
    bundle = extract_universe_semantics(ws, uni["id"])
    kg = semantic_to_graph_dict(bundle, uni["name"])
    sources_graph = {
        "nodes": [{"id": "u1", "kind": "Universe", "label": "Nebula"}],
        "edges": [],
    }
    canvas = GraphCanvas(
        sources_graph,
        export_dir=tmp_path / "exp",
        knowledge_graph=kg,
        workspace=ws,
        universe=uni,
    )
    assert "Universe" in canvas.sidebar.checks
    canvas.set_mode("knowledge")
    assert "Person" in canvas.sidebar.checks
    assert "Faction" in canvas.sidebar.checks
    assert "Chronologie" in canvas.sidebar.checks["Timeline"].text()
    canvas.close()
