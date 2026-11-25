"""Contract tests for stage 2: GraphEngine Map-Reduce, analysis, resume."""

from __future__ import annotations

import json

from aval_fakes import (
    LLM_RESPONSES,
    MINI_CHUNKS,
    FakeLlm,
    make_blueprint,
    run_engine,
    write_export,
)

from warframe_lore.v1.blueprint import load_blueprint
from warframe_lore.v1.graph_engine.engine import GraphEngine
from warframe_lore.v1.graph_engine.json_store import JsonGraphStore


def _entity_by_name(graph, name):
    return next(e for e in graph.entities.values() if e.name == name)


def test_extraction_fuses_entities_aliases_and_keeps_source_ids(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    valen = _entity_by_name(graph, "Commander Valen")
    assert "Shadow Blade" in valen.aliases
    assert valen.entity_type == "character"
    assert valen.attributes.get("role") == "commander"
    lyra = _entity_by_name(graph, "Lyra")
    assert "Dawn Singer" in lyra.aliases
    assert len(graph.entities) == 6
    for entity in graph.entities.values():
        for fact in entity.facts:
            assert fact.source_id in {"doc-a::0", "doc-a::1", "doc-b::0"}
    assert graph.sources["doc-a::0"].url == "https://example.org/lore/valen"


def test_alias_variants_merge_into_one_entity(tmp_path) -> None:
    responses = dict(LLM_RESPONSES)
    responses["doc-b::0"] = json.dumps(
        {
            "entities": [
                {"name": "shadow blade", "type": "character", "aliases": [],
                 "facts": [{"statement": "Shadow Blade survived the siege.",
                            "source_id": "doc-b::0", "arc": "Siege of Aurelia"}]}
            ],
            "relations": [],
        }
    )
    graph, _store = run_engine(tmp_path, llm=FakeLlm(responses))
    valen = _entity_by_name(graph, "Commander Valen")
    statements = [f.statement for f in valen.facts]
    assert "Shadow Blade survived the siege." in statements
    assert not any(e.name == "shadow blade" for e in graph.entities.values())


def test_relations_are_typed_directed_and_temporalized(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    valen = _entity_by_name(graph, "Commander Valen")
    covenant = _entity_by_name(graph, "Iron Covenant")
    lyra = _entity_by_name(graph, "Lyra")
    opposition = next(
        r for r in graph.relations
        if r.source_id_entity == lyra.id and r.target_id_entity == covenant.id
    )
    assert opposition.relation_type == "OPPOSES"
    assert opposition.arc_or_context == "Siege of Aurelia"
    assert "former ally" in opposition.dynamic_or_evolution
    assert opposition.source_ids == ["doc-a::1"]
    membership = next(
        r for r in graph.relations
        if r.source_id_entity == valen.id and r.target_id_entity == covenant.id
    )
    assert membership.relation_type == "BELONGS_TO"


def test_undeclared_types_are_rejected(tmp_path) -> None:
    responses = dict(LLM_RESPONSES)
    responses["doc-a::0"] = json.dumps(
        {
            "entities": [
                {"name": "Starship X", "type": "starship", "facts": []},
                {"name": "Commander Valen", "type": "character", "facts": []},
            ],
            "relations": [
                {"source": "Commander Valen", "target": "Starship X",
                 "type": "PILOTS", "source_id": "doc-a::0"}
            ],
        }
    )
    graph, _store = run_engine(tmp_path, llm=FakeLlm(responses))
    assert not any(e.name == "Starship X" for e in graph.entities.values())
    assert all(r.relation_type != "PILOTS" for r in graph.relations)


def test_analysis_finds_pivots_communities_and_bridges(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    analysis = graph.analysis
    assert analysis is not None
    covered = {eid for c in analysis.communities for eid in c.entity_ids}
    assert covered == set(graph.entities)
    assert len(analysis.communities) >= 2
    covenant = _entity_by_name(graph, "Iron Covenant")
    pivot = max(analysis.centrality, key=analysis.centrality.get)
    assert pivot == covenant.id
    for bridge in analysis.bridges:
        source_community = analysis.community_of(bridge.source_id_entity)
        target_community = analysis.community_of(bridge.target_id_entity)
        assert source_community.id != target_community.id
    assert analysis.bridges


def test_incremental_run_never_recalls_unchanged_chunks(tmp_path) -> None:
    llm = FakeLlm()
    graph, store = run_engine(tmp_path, llm=llm)
    first_calls = len(llm.calls)
    assert first_calls == 3
    export_dir = tmp_path / "export"
    engine = GraphEngine(make_blueprint(), llm, store, batch_size=1)
    graph_again = engine.run(export_dir)
    assert len(llm.calls) == first_calls
    assert set(graph_again.entities) == set(graph.entities)
    fresh_store = JsonGraphStore(tmp_path / "store")
    resumed = GraphEngine(make_blueprint(), llm, fresh_store, batch_size=1)
    resumed.run(export_dir)
    assert len(llm.calls) == first_calls


def test_changed_chunk_is_reextracted_alone(tmp_path) -> None:
    llm = FakeLlm()
    _graph, store = run_engine(tmp_path, llm=llm)
    changed = [dict(chunk) for chunk in MINI_CHUNKS]
    changed[1]["text"] = changed[1]["text"] + " A new oath is sworn."
    changed[1]["version"] = 2
    export_dir = write_export(tmp_path / "export", changed)
    engine = GraphEngine(make_blueprint(), llm, store, batch_size=1)
    engine.run(export_dir)
    assert llm.calls[3:] == ["doc-a::1"]


def test_failed_batch_is_retried_on_next_run(tmp_path) -> None:
    llm = FakeLlm(fail_chunks={"doc-a::1"})
    _graph, store = run_engine(tmp_path, llm=llm)
    manifest = store.load_manifest()
    assert "doc-a::1" not in manifest
    llm.fail_chunks = set()
    engine = GraphEngine(make_blueprint(), llm, store, batch_size=1)
    graph = engine.run(tmp_path / "export")
    assert "doc-a::1" in store.load_manifest()
    assert any(e.name == "Lyra" for e in graph.entities.values())


def test_example_blueprint_loads_without_pyyaml() -> None:
    blueprint = load_blueprint("warframe_lore/v1/configs/blueprint.example.yaml")
    assert blueprint.entity_types
    assert blueprint.relation_types
    assert blueprint.sections["micro"]["facts"]
    assert blueprint.vault["macro_note"] == "00_Vue_Globale.md"
