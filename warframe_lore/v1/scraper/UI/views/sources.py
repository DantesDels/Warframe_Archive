"""Sources tab: approved/active/suspended/blacklisted sources for one Universe."""

from __future__ import annotations

from tkinter import messagebox, simpledialog, ttk

from ..formatting import display_kind, display_percent, display_source_status
from ..security import validate_import
from .tables import add_table

COLUMNS = [
    ("location", "Emplacement", 420, True),
    ("kind", "Type", 110, False),
    ("status", "Statut", 120, False),
    ("score", "Pertinence", 85, False),
]


def add_tab(notebook, workspace, universe, on_change) -> None:
    sources = workspace.sources_for(universe["id"])
    frame = ttk.Frame(notebook, padding=8)
    ttk.Label(
        frame,
        text=(
            "Sources approuvées, actives, suspendues ou blacklistées "
            "pour cet Univers."
        ),
    ).pack(anchor="w", pady=(0, 6))
    rows = [
        (
            s["location"],
            display_kind(s["kind"]),
            display_source_status(s["status"]),
            display_percent(s["score"]),
        )
        for s in sources
    ]
    table = add_table(frame, COLUMNS, rows)
    table.source_ids = [s["id"] for s in sources]
    _actions(frame, table, workspace, universe, on_change)
    notebook.add(frame, text=f"Sources ({len(sources)})")


def _actions(frame, table, workspace, universe, on_change) -> None:
    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(6, 0))
    for label, status in (
        ("Activer", "approved"),
        ("Suspendre", "suspended"),
        ("Blacklister", "blacklisted"),
    ):
        ttk.Button(
            bar,
            text=label,
            command=lambda s=status: _set(table, workspace, on_change, s),
        ).pack(side="left", padx=(0, 4))
    ttk.Button(
        bar, text="Modifier", command=lambda: _edit(table, workspace, on_change),
    ).pack(side="left", padx=(0, 4))
    ttk.Button(
        bar, text="Supprimer", command=lambda: _delete(table, workspace, on_change),
    ).pack(side="left", padx=(0, 4))
    ttk.Button(
        bar, text="Ajouter une URL",
        command=lambda: _add(workspace, universe, on_change, True),
    ).pack(side="right")
    ttk.Button(
        bar, text="Importer un document",
        command=lambda: _add(workspace, universe, on_change, False),
    ).pack(side="right", padx=(0, 4))


def _selected(table) -> str | None:
    sel = table.selection()
    return table.source_ids[table.index(sel[0])] if sel else None


def _set(table, workspace, on_change, status: str) -> None:
    source_id = _selected(table)
    if source_id:
        workspace.update_source(
            source_id, status=status, selected=(status == "approved"),
        )
        on_change()


def _edit(table, workspace, on_change) -> None:
    source_id = _selected(table)
    if not source_id:
        return
    current = next(s for s in workspace.data["sources"] if s["id"] == source_id)
    answer = simpledialog.askstring(
        "Modifier la source", "Emplacement :", initialvalue=current["location"],
    )
    if answer and answer.strip():
        workspace.update_source(source_id, location=answer.strip())
        on_change()


def _delete(table, workspace, on_change) -> None:
    source_id = _selected(table)
    if source_id and messagebox.askyesno("Suppression", "Supprimer cette source ?"):
        workspace.delete_source(source_id)
        on_change()


def _add(workspace, universe, on_change, url_mode: bool) -> None:
    label = "URL de la source :" if url_mode else "Chemin du document à importer :"
    title = "Ajouter une URL" if url_mode else "Importer un document"
    value = simpledialog.askstring(title, label)
    if not value or not value.strip():
        return
    ok, reason = validate_import(value.strip())
    if not ok:
        messagebox.showerror("Sécurité à l'import", reason)
        return
    kind = "website" if url_mode else "document"
    workspace.add_manual_source(universe["id"], value.strip(), kind=kind)
    on_change()
