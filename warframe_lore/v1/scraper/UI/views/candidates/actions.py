"""Bulk and single-item curation actions triggered from the candidates table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ...security import validate_import
from ..simple_table import SimpleTable
from .preview_worker import start_preview


def _activate_candidate(workspace: Any, candidate_id: str) -> None:
    candidate = workspace._candidate(candidate_id)
    uid = str(candidate.get("universeId", ""))
    location = str(candidate.get("location", "")).strip()
    existing = next(
        (
            s for s in workspace.sources_for(uid)
            if str(s.get("location", "")).strip() == location
        ),
        None,
    )
    if existing is not None:
        workspace.update_source(str(existing["id"]), status="approved", selected=True)
        workspace.update_candidate(candidate_id, status="active")
        return
    workspace.add_source_from_candidate(candidate_id)


def _blacklist_candidate(workspace: Any, candidate_id: str) -> None:
    workspace.delete_source(f"src-{candidate_id}")
    workspace.update_candidate(candidate_id, status="blacklisted")


STATUS_HANDLERS = {
    "active": _activate_candidate,
    "blacklisted": _blacklist_candidate,
    "suspended": lambda workspace, cid: workspace.update_candidate(
        cid, status="suspended"
    ),
}


def apply_status(
    table: SimpleTable, workspace: Any, on_change: Callable[[], None], status: str
) -> None:
    """Apply a lifecycle status to every currently selected candidate."""
    candidate_ids = table.selected_ids()
    if not candidate_ids:
        return
    handler = STATUS_HANDLERS[status]
    for candidate_id in candidate_ids:
        handler(workspace, candidate_id)
    on_change()


def remove_candidate(
    table: SimpleTable,
    workspace: Any,
    _universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Remove all selected candidates and their derived sources."""
    candidate_ids = table.selected_ids()
    if not candidate_ids:
        return
    for candidate_id in candidate_ids:
        workspace.delete_source(f"src-{candidate_id}")
        workspace.remove_candidate(candidate_id)
    on_change()


def preview_children(
    table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Discover child URLs of the first selected candidate for manual review."""
    candidate_id = table.selected_id()
    candidates = cast(
        list[dict[str, Any]], workspace.candidates_for(str(universe["id"]))
    )
    candidate = next(
        (item for item in candidates if str(item.get("id")) == candidate_id), None
    )
    if not candidate:
        return
    start_preview(
        table, workspace, universe, str(candidate.get("location", "")), on_change
    )


def add_manual(
    _table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Add a manually entered URL or local path after the security gate."""
    value, ok = QInputDialog.getText(
        None, "Ajout manuel", "URL ou chemin du document :"
    )
    if not ok or not value.strip():
        return
    location = value.strip()
    allowed, reason = validate_import(location)
    if not allowed:
        QMessageBox.critical(None, "Sécurité à l'import", reason)
        return
    workspace.add_manual_source(str(universe["id"]), location)
    on_change()
