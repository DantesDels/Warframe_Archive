"""Candidates tab: discovered sources awaiting user curation."""

from __future__ import annotations

from tkinter import ttk

from ..actions import curation_actions as actions
from ..formatting import display_kind, display_percent, display_source_status
from .tables import add_table

COLUMNS = [
    ("title", "Titre", 220, True),
    ("location", "Emplacement", 360, True),
    ("kind", "Type", 110, False),
    ("score", "Pertinence", 85, False),
    ("status", "État", 110, False),
]


def add_tab(notebook, workspace, universe, on_change) -> None:
    candidates = workspace.candidates_for(universe["id"])
    frame = ttk.Frame(notebook, padding=8)
    ttk.Label(
        frame,
        text=(
            "Sources découvertes en attente de validation "
            "ou filtrées par le seuil n %."
        ),
    ).pack(anchor="w", pady=(0, 6))
    rows = [
        (
            c["title"],
            c["location"],
            display_kind(c["kind"]),
            display_percent(c["score"]),
            display_source_status(c["status"]),
        )
        for c in candidates
    ]
    table = add_table(frame, COLUMNS, rows)
    table.candidate_ids = [c["id"] for c in candidates]
    _actions(frame, table, workspace, universe, on_change)
    notebook.add(frame, text=f"Candidats ({len(candidates)})")


def _actions(frame, table, workspace, universe, on_change) -> None:
    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(6, 0))
    buttons = (
        ("Activer", lambda: actions.apply_status(
            table, workspace, on_change, "active")),
        ("Suspendre", lambda: actions.apply_status(
            table, workspace, on_change, "suspended")),
        ("Blacklister", lambda: actions.apply_status(
            table, workspace, on_change, "blacklisted")),
        ("Modifier", lambda: actions.edit_location(table, workspace, on_change)),
        ("Forcer MÀJ", lambda: actions.force_update(table, workspace, on_change)),
        ("Supprimer", lambda: actions.remove_candidate(
            table, workspace, on_change)),
    )
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side="left", padx=(0, 4))
    ttk.Button(
        bar,
        text="+ Ajout manuel",
        command=lambda: actions.add_manual_source(workspace, universe, on_change),
    ).pack(side="right")
