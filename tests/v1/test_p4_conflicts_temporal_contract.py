"""Contract tests for Phase P4: conflicts resolution, trust & temporal truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from warframe_lore.v1.scraper.adapters.outbound.llm.openai_compat import (
    OpenAiCompatLlmAdapter,
)
from warframe_lore.v1.scraper.capabilities.models import LlmBudget
from warframe_lore.v1.scraper.truth import (
    analyze_docs_truth,
    analyze_universe_truth,
    conflicts_for,
    export_truth_report,
    extract_doc_claims,
    infer_trust_profile,
    open_conflicts_count,
    resolve_conflict,
    set_source_trust_profile,
    trust_label,
    trust_weight,
)
from warframe_lore.v1.scraper.UI.artifacts import emit_artifacts
from warframe_lore.v1.scraper.UI.workspace import WorkshopWorkspace


def test_trust_profiles_inference_weights_and_persistence(tmp_path: Path) -> None:
    assert trust_weight("official") > trust_weight("documentation")
    assert trust_weight("documentation") > trust_weight("community_wiki")
    assert trust_weight("community_wiki") > trust_weight("third_party")
    assert trust_label("official") == "Officiel"
    assert trust_label("community_wiki") == "Wiki communautaire"

    assert infer_trust_profile({}, "https://docs.example.org/guide") == "documentation"
    assert infer_trust_profile({}, "https://lore.fandom.com/wiki/A") == "community_wiki"
    off = infer_trust_profile({"relevance": 0.92}, "https://example.com/")
    assert off == "official"
    assert infer_trust_profile({}, "https://random-blog.example.net/p") == "third_party"

    ws = WorkshopWorkspace(path=tmp_path / "ws.json")
    uni = ws.create("Astral")
    ws.data["sources"].append(
        {"id": "src-1", "universeId": uni["id"], "location": "https://blog.test/a"}
    )
    assert set_source_trust_profile(ws, "src-1", "official") is True
    assert infer_trust_profile(ws.data["sources"][0]) == "official"


def test_claim_extraction_temporal_supersession_and_cross_source_conflict() -> None:
    sources = [
        {
            "id": "src-official",
            "location": "https://studio.example.com/news",
            "trustProfile": "official",
        },
        {
            "id": "src-wiki",
            "location": "https://wiki.example.org/wiki/Valkyr",
            "trustProfile": "community_wiki",
        },
    ]
    docs = [
        # Same official source updates Citadel Helios release year 2021 -> 2022
        {
            "id": "doc-o1",
            "sourceId": "src-official",
            "url": "https://studio.example.com/news/1",
            "updatedAt": "2021-06-01T00:00:00Z",
            "content": (
                "Citadel Helios was released in 2021. "
                "Solar Forge was created by Guild Alpha."
            ),
        },
        {
            "id": "doc-o2",
            "sourceId": "src-official",
            "url": "https://studio.example.com/news/2",
            "updatedAt": "2022-03-01T00:00:00Z",
            "content": "Citadel Helios was released in 2022.",
        },
        # Community wiki disagrees on Solar Forge creator & Citadel Helios year
        {
            "id": "doc-w1",
            "sourceId": "src-wiki",
            "url": "https://wiki.example.org/wiki/Solar",
            "updatedAt": "2022-04-01T00:00:00Z",
            "content": (
                "Citadel Helios was released in 2020. "
                "Solar Forge was created by Guild Beta."
            ),
        },
    ]

    claims = extract_doc_claims(docs[0], trust_profile="official")
    assert any(c.predicate == "release_year" and c.value == "2021" for c in claims)
    assert all(c.chunk_id.startswith("doc-o1::") for c in claims)

    report = analyze_docs_truth(docs, sources, "u-astral")
    assert len(report.history) == 1
    assert report.history[0].old_value == "2021"
    assert report.history[0].new_value == "2022"
    obsolete = [c for c in report.claims if c.status == "obsolete"]
    assert len(obsolete) == 1
    assert obsolete[0].value == "2021" and obsolete[0].superseded_by

    assert len(report.conflicts) == 2
    for conflict in report.conflicts:
        assert conflict.status == "open"
        assert conflict.recommended == "keep_a"
        assert conflict.source_a_profile == "official"
        assert conflict.source_b_profile == "community_wiki"


def test_llm_verification_runs_only_on_candidate_conflicts() -> None:
    calls = 0

    class FakeResp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "contradiction",
                                    "winner": "A",
                                    "rationale": "Official source takes precedence.",
                                }
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 55},
            }

    class FakeHttp:
        def post(self, *_args: Any, **_kwargs: Any) -> FakeResp:
            nonlocal calls
            calls += 1
            return FakeResp()

    adapter = OpenAiCompatLlmAdapter(
        LlmBudget(enabled=True, model="mock-fc", max_tokens=1000, max_calls=5),
        http_client=FakeHttp(),
    )

    # No conflicts -> 0 LLM calls
    clean_docs = [
        {"id": "d1", "sourceId": "s1", "content": "Citadel Nova was released in 2023."}
    ]
    report_clean = analyze_docs_truth(clean_docs, [], "u1", llm_adapter=adapter)
    assert len(report_clean.conflicts) == 0
    assert calls == 0

    # One conflict -> exactly 1 LLM call
    conflict_docs = [
        {"id": "d1", "sourceId": "s1", "content": "Citadel Nova was released in 2023."},
        {"id": "d2", "sourceId": "s2", "content": "Citadel Nova was released in 2021."},
    ]
    report_conf = analyze_docs_truth(conflict_docs, [], "u1", llm_adapter=adapter)
    assert len(report_conf.conflicts) == 1
    assert calls == 1
    assert "contradiction" in report_conf.conflicts[0].llm_verdict
    assert report_conf.stats["llm_verified"] == 1


def test_human_arbitration_preserved_and_exports_written(tmp_path: Path) -> None:
    ws = WorkshopWorkspace(path=tmp_path / "workspace.json")
    uni = ws.create("Horizons")
    uid = uni["id"]
    ws.data["sources"].extend(
        [
            {"id": "s-off", "universeId": uid, "trustProfile": "official"},
            {"id": "s-tp", "universeId": uid, "trustProfile": "third_party"},
        ]
    )
    ws.data["documents"].extend(
        [
            {
                "id": "d-1",
                "universeId": uid,
                "sourceId": "s-off",
                "url": "https://official.example/a",
                "content": "Star Gate is located in Sector Alpha.",
            },
            {
                "id": "d-2",
                "universeId": uid,
                "sourceId": "s-tp",
                "url": "https://blog.example/a",
                "content": "Star Gate is located in Sector Omega.",
            },
        ]
    )
    ws.save()

    report = analyze_universe_truth(ws, uid)
    assert open_conflicts_count(ws, uid) == 1
    cid = report.conflicts[0].id

    resolved = resolve_conflict(ws, uid, cid, "keep_a", note="Officiel validé")
    assert resolved is not None
    assert resolved["status"] == "resolved_a"
    assert open_conflicts_count(ws, uid) == 0

    # Re-running analysis preserves prior human arbitration
    analyze_universe_truth(ws, uid)
    assert conflicts_for(ws, uid)[0]["status"] == "resolved_a"
    assert open_conflicts_count(ws, uid) == 0

    out = tmp_path / "truth_out"
    paths = export_truth_report(out, uni, report)
    assert {p.name for p in paths} == {
        "claims.jsonl",
        "conflicts.json",
        "temporal_history.json",
        "truth_summary.json",
    }

    # Opt-in emit_artifacts wiring
    m_off = emit_artifacts(tmp_path / "run_off", uni, ws.data["documents"], ["json"])
    assert not any(f["name"] == "conflicts.json" for f in m_off["files"])

    m_on = emit_artifacts(
        tmp_path / "run_on",
        uni,
        ws.data["documents"],
        ["json"],
        fact_check_config={"enabled": True, "model": ""},
        sources=ws.data["sources"],
    )
    assert any(f["name"] == "conflicts.json" for f in m_on["files"])
    assert (tmp_path / "run_on" / "truth" / "claims.jsonl").is_file()


def test_ui_conflicts_tab_trust_dialog_and_fact_check_capability(
    tmp_path: Path,
) -> None:
    from PySide6.QtWidgets import QApplication, QTabWidget

    from warframe_lore.v1.scraper.UI.dialogs.capabilities_dialog import (
        CapabilitiesDialog,
    )
    from warframe_lore.v1.scraper.UI.views.conflicts import (
        TrustProfilesDialog,
        conflicts_view,
    )
    from warframe_lore.v1.scraper.UI.views.details import DetailPane

    app = QApplication.instance() or QApplication([])
    assert app is not None

    dlg = CapabilitiesDialog(None, {})
    assert "fact_check" in dlg._toggles
    dlg._toggles["fact_check"].setChecked(True)
    assert dlg.llm_budget_box.isEnabled()
    dlg.llm_budget_box.model_input.setText("fact-llm")
    dlg._save()
    assert dlg.result_capabilities is not None
    assert dlg.result_capabilities["fact_check"]["enabled"] is True
    assert dlg.result_capabilities["fact_check"]["model"] == "fact-llm"

    ws = WorkshopWorkspace(path=tmp_path / "ws_ui.json")
    uni = ws.create("Sol")
    uid = uni["id"]
    ws.data["sources"].extend(
        [
            {"id": "s1", "universeId": uid, "location": "https://a.example/x"},
            {"id": "s2", "universeId": uid, "location": "https://wiki.example/x"},
        ]
    )
    ws.data["documents"].extend(
        [
            {
                "id": "d1", "universeId": uid, "sourceId": "s1",
                "content": "Titan Core was created by House Sol.",
            },
            {
                "id": "d2", "universeId": uid, "sourceId": "s2",
                "content": "Titan Core was created by House Nox.",
            },
        ]
    )
    analyze_universe_truth(ws, uid)

    trust_dlg = TrustProfilesDialog(None, ws, uid)
    trust_dlg._combos["s1"].setCurrentIndex(0)
    trust_dlg._save()
    assert ws.data["sources"][0]["trustProfile"] == "official"

    tab = conflicts_view(ws, uni, lambda: None)
    assert tab.findChild(object, "AnalyzeConflictsButton") is not None
    assert tab.findChild(object, "KeepAButton") is not None

    pane = DetailPane()
    pane.show_universe(uni, ws, lambda: None)
    tabs = pane.findChild(QTabWidget)
    assert tabs is not None
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert any(label.startswith("Conflits (1)") for label in labels)
    pane.close()
