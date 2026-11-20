"""Action callbacks for the candidate curation panel."""

from __future__ import annotations

from tkinter import messagebox, simpledialog

from ..security import validate_import


def selected_candidate(table) -> str | None:
    """Return the id of the highlighted candidate, if any."""
    selection = table.selection()
    return table.candidate_ids[table.index(selection[0])] if selection else None


def apply_status(table, workspace, on_change, status: str) -> None:
    """Apply a curation decision to the selected candidate."""
    candidate_id = selected_candidate(table)
    if not candidate_id:
        return
    if status == "active":
        workspace.add_source_from_candidate(candidate_id)
    elif status == "blacklisted":
        workspace.delete_source(f"src-{candidate_id}")
    else:
        workspace.update_candidate(candidate_id, status=status)
    on_change()


def remove_candidate(table, workspace, on_change) -> None:
    """Drop a proposition and its imported source."""
    candidate_id = selected_candidate(table)
    if candidate_id:
        workspace.delete_source(f"src-{candidate_id}")
        workspace.remove_candidate(candidate_id)
        on_change()


def force_update(table, workspace, on_change) -> None:
    """Toggle the forced-refresh flag of a candidate."""
    candidate_id = selected_candidate(table)
    if candidate_id:
        current = workspace._candidate(candidate_id)["forceUpdate"]
        workspace.update_candidate(candidate_id, forceUpdate=not current)
        on_change()


def edit_location(table, workspace, on_change) -> None:
    """Let the user correct a candidate URL or path."""
    candidate_id = selected_candidate(table)
    if not candidate_id:
        return
    location = workspace._candidate(candidate_id)["location"]
    answer = simpledialog.askstring(
        "Modifier la source", "Emplacement :", initialvalue=location,
    )
    if answer and answer.strip():
        workspace.update_candidate(candidate_id, location=answer.strip())
        on_change()


def add_manual_source(workspace, universe, on_change) -> None:
    """Register a source typed by the user after security validation."""
    location = simpledialog.askstring(
        "Ajout manuel", "URL ou chemin du document :",
    )
    if not location or not location.strip():
        return
    ok, reason = validate_import(location.strip())
    if not ok:
        messagebox.showerror("Sécurité à l'import", reason)
        return
    workspace.add_manual_source(universe["id"], location.strip())
    on_change()
