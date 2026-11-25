"""Contract tests for stage 3: vault synthesis, autolink, incremental, locks."""

from __future__ import annotations

import json

from aval_fakes import make_blueprint, run_engine

from warframe_lore.v1.graph_engine.models import Fact
from warframe_lore.v1.synthesizer.autolink import autolink
from warframe_lore.v1.synthesizer.canvas import community_canvas, macro_canvas
from warframe_lore.v1.synthesizer.frontmatter import parse_frontmatter
from warframe_lore.v1.synthesizer.mermaid import entity_mermaid
from warframe_lore.v1.synthesizer.synthesizer import ObsidianSynthesizer
from warframe_lore.v1.synthesizer.vault import ObsidianVaultExporter


def _synthesize(tmp_path, graph):
    exporter = ObsidianVaultExporter(tmp_path / "vault")
    report = ObsidianSynthesizer(make_blueprint(), exporter).synthesize(graph)
    return exporter, report


def _entity_by_name(graph, name):
    return next(e for e in graph.entities.values() if e.name == name)


def test_vault_tree_indexes_and_frontmatter(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    exporter, report = _synthesize(tmp_path, graph)
    assert report.written
    assert exporter.read_note("00_Index.md") is not None
    assert exporter.read_note("00_Vue_Globale.md") is not None
    assert exporter.read_note("01_Characters/_Index.md") is not None
    note = exporter.read_note("01_Characters/commander-valen.md")
    assert note is not None
    fields, body = parse_frontmatter(note)
    valen = _entity_by_name(graph, "Commander Valen")
    assert fields["id"] == valen.id
    assert fields["type"] == "character"
    assert "Shadow Blade" in fields["aliases"]
    assert fields["tags"] == ["character"]
    assert fields["sources_count"] >= 1
    assert fields["content_hash"]
    assert fields["locked"] is False
    assert "> [!cite]- Sources" in body
    assert "| Cible |" in body or "| Target |" in body or "|" in body


def test_micro_note_has_mermaid_and_relation_table(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    exporter, _report = _synthesize(tmp_path, graph)
    valen = _entity_by_name(graph, "Commander Valen")
    note = exporter.read_note("01_Characters/commander-valen.md")
    assert "```mermaid" in note
    assert "graph LR" in note
    assert "-->|member of|" in note
    mermaid = entity_mermaid(graph, valen.id, make_blueprint())
    assert mermaid.startswith("graph LR")
    assert valen.id.replace("-", "_") in mermaid


def test_autolink_respects_protected_zones(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    entities = list(graph.entities.values())
    text = (
        "---\ntitle: Lyra mentions\n---\n"
        "# Lyra heading\n"
        "Lyra met Shadow Blade in Sector Aurelia.\n"
        "```\nLyra code block\n```\n"
        "Inline `Lyra code` stays.\n"
        "Existing [[Lyra]] link stays.\n"
    )
    linked = autolink(text, entities, self_name="Lyra")
    assert "[[Commander Valen|Shadow Blade]]" in linked
    assert "[[Sector Aurelia]]" in linked
    assert "# Lyra heading" in linked
    assert "title: Lyra mentions" in linked
    assert "```\nLyra code block\n```" in linked
    assert "`Lyra code`" in linked
    assert "Existing [[Lyra]] link stays." in linked
    assert "[[Lyra]] met" not in linked


def test_canvases_are_valid_json_with_groups_and_labels(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    exporter, _report = _synthesize(tmp_path, graph)
    blueprint = make_blueprint()
    note_paths = {
        eid: f"{blueprint.folder_for(e.entity_type)}/{e.id}.md"
        for eid, e in graph.entities.items()
    }
    macro = macro_canvas(graph, blueprint, note_paths)
    assert any(node["type"] == "group" for node in macro["nodes"])
    assert macro["edges"]
    assert all(edge["label"] for edge in macro["edges"])
    community = graph.analysis.communities[0]
    local = community_canvas(graph, community, blueprint, note_paths)
    json.dumps(local)
    macro_files = [
        path for path in exporter.list_notes() if path.endswith(".canvas")
    ]
    assert not macro_files
    canvas_paths = [
        path
        for path in (tmp_path / "vault").rglob("*.canvas")
    ]
    assert len(canvas_paths) == len(graph.analysis.communities) + 1
    for path in canvas_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "nodes" in payload and "edges" in payload


def test_meso_and_macro_notes_anchor_on_graph(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    exporter, _report = _synthesize(tmp_path, graph)
    meso_notes = [
        path for path in exporter.list_notes() if path.startswith("06_Arcs/")
    ]
    assert len(meso_notes) == len(graph.analysis.communities)
    macro = exporter.read_note("00_Vue_Globale.md")
    assert "Iron Covenant" in macro
    assert "Bridges between arcs" in macro
    assert "Master timeline" in macro
    assert "[[Siege of Aurelia]]" in macro


def test_incremental_sync_only_rewrites_changed_notes(tmp_path) -> None:
    graph, store = run_engine(tmp_path)
    exporter, first = _synthesize(tmp_path, graph)
    assert first.written
    _exporter2, second = _synthesize(tmp_path, graph)
    assert not second.written
    assert second.up_to_date
    valen = _entity_by_name(graph, "Commander Valen")
    valen.facts.append(
        Fact(statement="A new fact appears.", source_id="doc-a::0", arc_or_context="")
    )
    store.save_graph(graph)
    _exporter3, third = _synthesize(tmp_path, graph)
    assert "01_Characters/commander-valen.md" in third.written
    assert "02_Factions/iron-covenant.md" in third.up_to_date


def test_locked_note_is_never_overwritten(tmp_path) -> None:
    graph, _store = run_engine(tmp_path)
    exporter, _first = _synthesize(tmp_path, graph)
    note_path = "01_Characters/commander-valen.md"
    original = exporter.read_note(note_path)
    locked_content = original.replace("locked: false", "locked: true")
    locked_content += "\nHuman edit to preserve.\n"
    exporter.write_note(note_path, locked_content)
    valen = _entity_by_name(graph, "Commander Valen")
    valen.facts.append(
        Fact(statement="Upstream change.", source_id="doc-a::0", arc_or_context="")
    )
    _exporter2, report = _synthesize(tmp_path, graph)
    assert note_path in report.locked
    assert note_path not in report.written
    assert exporter.read_note(note_path) == locked_content
