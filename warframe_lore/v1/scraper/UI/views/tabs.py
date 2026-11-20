"""Tab builders for the Universe detail pane."""

from __future__ import annotations

from tkinter import ttk

from ..formatting import display_percent, display_run_status
from . import candidates, sources
from .tables import add_table

DOC_COLS = [
    ("title", "Titre", 260, True),
    ("docType", "Type", 120, False),
    ("language", "Langue", 80, False),
    ("relevance", "Pertinence", 85, False),
    ("duplicate", "Doublon", 80, False),
]
RUN_COLS = [
    ("id", "Exécution", 160, True),
    ("date", "Date", 110, False),
    ("status", "Statut", 110, False),
    ("emitted", "Émis", 70, False),
]


def add_sources_tab(notebook, workspace, universe, on_change) -> None:
    sources.add_tab(notebook, workspace, universe, on_change)


def add_documents_tab(notebook, workspace, universe) -> None:
    documents = workspace.documents_for(universe["id"])
    frame = ttk.Frame(notebook, padding=8)
    rows = [
        (
            d["title"],
            d["docType"],
            d["language"],
            display_percent(d["relevance"]),
            "Oui" if d["isDuplicate"] else "Non",
        )
        for d in documents
    ]
    add_table(frame, DOC_COLS, rows)
    notebook.add(frame, text=f"Documents ({len(documents)})")


def add_runs_tab(notebook, workspace, universe) -> None:
    runs = workspace.runs_for(universe["id"])
    frame = ttk.Frame(notebook, padding=8)
    rows = [
        (
            r["id"],
            r["startedAt"][:10],
            display_run_status(r["status"]),
            r["counts"]["emitted"],
        )
        for r in runs
    ]
    add_table(frame, RUN_COLS, rows)
    notebook.add(frame, text=f"Exécutions ({len(runs)})")


def add_candidates_tab(notebook, workspace, universe, on_change) -> None:
    candidates.add_tab(notebook, workspace, universe, on_change)
