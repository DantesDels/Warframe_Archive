"""Curation actions triggered from the candidates table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ....collect.http import HttpClient
from ....use_cases.review_children import preview_child_candidates
from ...security import validate_import
from ..simple_table import SimpleTable

STATUS_HANDLERS = {
    "active": lambda workspace, cid: workspace.add_source_from_candidate(cid),
    "blacklisted": lambda workspace, cid: workspace.delete_source(f"src-{cid}"),
    "suspended": lambda workspace, cid: workspace.update_candidate(
        cid, status="suspended"
    ),
}


def apply_status(
    table: SimpleTable, workspace: Any, on_change: Callable[[], None], status: str
) -> None:
    """Move the selected candidate to the requested lifecycle status."""
    candidate_id = table.selected_id()
    if candidate_id:
        STATUS_HANDLERS[status](workspace, candidate_id)
        on_change()


def remove_candidate(
    table: SimpleTable,
    workspace: Any,
    _universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Remove a rejected candidate and its derived source."""
    candidate_id = table.selected_id()
    if candidate_id:
        workspace.delete_source(f"src-{candidate_id}")
        workspace.remove_candidate(candidate_id)
        on_change()


def preview_children(
    table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Discover child URLs of the selected source for manual review."""
    candidate_id = table.selected_id()
    candidates = cast(
        list[dict[str, Any]], workspace.candidates_for(str(universe["id"]))
    )
    candidate = next(
        (item for item in candidates if str(item.get("id")) == candidate_id), None
    )
    if not candidate:
        return
    try:
        children = preview_child_candidates(
            workspace, universe, str(candidate.get("location", "")), client=HttpClient()
        )
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(
            None, "Prévisualisation", f"Impossible de prévisualiser : {exc}"
        )
        return
    QMessageBox.information(
        None,
        "Prévisualisation",
        f"{len(children)} page(s) enfant(s) ajoutée(s) comme candidats à valider.",
    )
    on_change()


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
