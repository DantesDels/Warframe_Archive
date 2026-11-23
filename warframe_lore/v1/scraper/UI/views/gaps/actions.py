"""Human-in-the-loop curation actions for the Lacunes (KnowledgeGap) tab."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QInputDialog, QLabel, QMessageBox, QPushButton, QWidget

from ....gaps import (
    KnowledgeGap,
    gaps_for,
    gaps_jsonl_path,
    ingest_jsonl,
    record_gap,
    remove_gaps,
    start_gaps_server,
    update_gap_status,
)
from ....settings import Settings
from ..simple_table import SimpleTable
from .worker import GapDiscoveryWorker


def add_manual_gap(
    parent: QWidget, workspace: Any, uid: str, on_change: Callable[[], None]
) -> None:
    """Prompt the user for an unanswered question and store it as a gap."""
    prompt = "Question sans réponse ou sujet manquant pour cet Univers :"
    question, ok = QInputDialog.getText(parent, "Ajouter une lacune", prompt)
    if ok and question.strip():
        record_gap(workspace, uid, question.strip(), confidence=0.0, source="manual")
        on_change()


def import_gaps_file(
    parent: QWidget, workspace: Any, uid: str, on_change: Callable[[], None]
) -> None:
    """Ingest gaps from data/v1/gaps.jsonl into the workspace."""
    path = gaps_jsonl_path(workspace)
    if not path.is_file():
        QMessageBox.information(
            parent,
            "Import gaps.jsonl",
            f"Aucun fichier trouvé : {path}\nÉcrivez une ligne JSON par question "
            '({"universe_id", "question", "confidence"}).',
        )
        return
    items = ingest_jsonl(workspace, path, default_universe_id=uid)
    QMessageBox.information(
        parent, "Import gaps.jsonl", f"{len(items)} lacune(s) importée(s)."
    )
    on_change()


def apply_gap_status(
    table: SimpleTable, workspace: Any, status: str, on_change: Callable[[], None]
) -> None:
    """Apply a lifecycle status to all selected KnowledgeGaps."""
    ids = table.selected_ids()
    if ids and update_gap_status(workspace, ids, status):
        on_change()


def delete_selected_gaps(
    table: SimpleTable, workspace: Any, on_change: Callable[[], None]
) -> None:
    """Delete all selected KnowledgeGaps."""
    ids = table.selected_ids()
    if ids and remove_gaps(workspace, ids):
        on_change()


def launch_gap_discovery(
    parent: QWidget,
    table: SimpleTable,
    workspace: Any,
    uid: str,
    status_label: QLabel,
    on_change: Callable[[], None],
    workers: list[GapDiscoveryWorker],
) -> None:
    """Launch background targeted discovery for selected KnowledgeGaps."""
    ids = set(table.selected_ids())
    if not ids:
        return
    selected = [
        KnowledgeGap.from_dict(g)
        for g in gaps_for(workspace, uid)
        if str(g.get("id", "")) in ids
    ]
    if not selected:
        return
    status_label.setText(
        f"Découverte ciblée en cours pour {len(selected)} lacune(s)..."
    )
    worker = GapDiscoveryWorker(workspace, selected, Settings())
    workers.append(worker)

    def _done(count: int, err: str) -> None:
        if err:
            status_label.setText(f"Erreur découverte lacunes : {err}")
            return
        status_label.setText(f"{count} candidat(s) ajouté(s) dans Candidats.")
        on_change()

    worker.finished_discovery.connect(_done)
    worker.start()


def stop_gaps_endpoint(workspace: Any) -> None:
    """Stop any running local /gaps HTTP server attached to the workspace."""
    handle = getattr(workspace, "_gaps_server", None)
    if handle is not None:
        handle.stop()
        workspace._gaps_server = None


def toggle_gaps_endpoint(
    workspace: Any,
    button: QPushButton,
    status_label: QLabel,
    *,
    port: int = 8766,
) -> None:
    """Start or stop the local POST /gaps HTTP endpoint for RAG/bot ingestion."""
    handle = getattr(workspace, "_gaps_server", None)
    if handle is not None:
        stop_gaps_endpoint(workspace)
        button.setText("Démarrer /gaps")
        button.setToolTip("Démarrer le serveur HTTP local POST /gaps pour bots/RAG")
        status_label.setText("Endpoint local /gaps arrêté.")
        return
    try:
        handle = start_gaps_server(workspace, host="127.0.0.1", port=port)
    except OSError as exc:
        status_label.setText(f"Impossible de démarrer /gaps : {exc}")
        return
    workspace._gaps_server = handle
    button.setText("Arrêter /gaps")
    button.setToolTip(f"Actif sur {handle.url} — cliquer pour arrêter")
    status_label.setText(f"Endpoint actif : POST {handle.url}")
