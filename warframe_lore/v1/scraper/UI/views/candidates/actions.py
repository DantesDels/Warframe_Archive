"""Bulk and single-item curation actions triggered from the candidates table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ...security import validate_import
from ..simple_table import SimpleTable
from .bulk import apply_bulk_status, batch_context, drop_sources
from .preview_worker import start_preview


def apply_status(
    table: SimpleTable, workspace: Any, on_change: Callable[[], None], status: str
) -> None:
    """Apply a lifecycle status to all selected candidates in one batch."""
    candidate_ids = table.selected_ids()
    if not candidate_ids:
        return
    apply_bulk_status(workspace, candidate_ids, status)
    on_change()


def remove_candidate(
    table: SimpleTable,
    workspace: Any,
    _universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    """Remove all selected candidates and their derived sources in one save."""
    candidate_ids = set(table.selected_ids())
    if not candidate_ids:
        return
    with batch_context(workspace):
        workspace.data["candidates"] = [
            c for c in cast(list[dict[str, Any]], workspace.data.get("candidates", []))
            if str(c.get("id", "")) not in candidate_ids
        ]
        drop_sources(workspace, {f"src-{cid}" for cid in candidate_ids})
        if hasattr(workspace, "save"):
            workspace.save()
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
    if candidate:
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
