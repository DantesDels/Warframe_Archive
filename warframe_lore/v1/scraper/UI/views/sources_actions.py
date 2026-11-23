"""Action handlers for the sources tab with single-save batch mutations."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
)

from ..security import validate_import


def _batch(workspace: Any) -> Any:
    return workspace.batch_save() if hasattr(workspace, "batch_save") else nullcontext()


def build_actions(view: Any) -> QHBoxLayout:
    bar = QHBoxLayout()
    view._suspend_btn = QPushButton("Suspendre")
    view._suspend_btn.clicked.connect(lambda: toggle_suspend(view))
    for label, slot in (
        ("+ Ajouter URL", lambda: add_url(view)),
        ("+ Importer fichier", lambda: import_file(view)),
        ("+ Importer dossier", lambda: import_directory(view)),
    ):
        btn = QPushButton(label)
        btn.clicked.connect(slot)
        bar.addWidget(btn)
    bar.addWidget(view._suspend_btn)
    for label, slot in (
        ("Modifier", lambda: edit_source(view)),
        ("Supprimer", lambda: delete_source(view)),
        ("Blacklister", lambda: blacklist_source(view)),
        ("Forcer MAJ", lambda: force_update(view)),
    ):
        button = QPushButton(label)
        button.clicked.connect(slot)
        bar.addWidget(button)
    bar.addStretch(1)
    return bar


def add_url(view: Any) -> None:
    value, ok = QInputDialog.getText(view, "Ajouter une URL", "URL de la source :")
    if ok and value.strip():
        _add_location(view, value.strip(), "website")


def import_file(view: Any) -> None:
    path, _ = QFileDialog.getOpenFileName(view, "Importer un fichier")
    if path:
        _add_location(view, path, "document")


def import_directory(view: Any) -> None:
    """Add a local directory as a recursive structured-document source."""
    path = QFileDialog.getExistingDirectory(view, "Importer un dossier")
    if path:
        _add_location(view, path, "local_directory")


def _add_location(view: Any, location: str, kind: str) -> None:
    allowed, reason = validate_import(location)
    if not allowed:
        QMessageBox.critical(view, "Sécurité à l'import", reason)
        return
    view.workspace.add_manual_source(str(view.universe["id"]), location, kind=kind)
    view.on_change()


def toggle_suspend(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    all_susp = all(str(s.get("status")) == "suspended" for s in sources)
    status = "approved" if all_susp else "suspended"
    with _batch(view.workspace):
        for src in sources:
            view.workspace.update_source(
                str(src["id"]), status=status, selected=status == "approved"
            )
    view.on_change()


def edit_source(view: Any) -> None:
    source = cast(dict[str, Any] | None, view.current_source())
    if not source:
        return
    loc = str(source.get("location", ""))
    value, ok = QInputDialog.getText(view, "Modifier", "Emplacement :", text=loc)
    if ok and value.strip():
        view.workspace.update_source(str(source["id"]), location=value.strip())
        view.on_change()


def delete_source(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    n = len(sources)
    msg = f"Supprimer {n} sources ?" if n > 1 else "Supprimer la source ?"
    if QMessageBox.question(view, "Suppression", msg) != QMessageBox.StandardButton.Yes:
        return
    with _batch(view.workspace):
        for src in sources:
            view.workspace.delete_source(str(src["id"]))
    view.on_change()


def blacklist_source(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    with _batch(view.workspace):
        for src in sources:
            sid = str(src["id"])
            view.workspace.update_source(sid, status="blacklisted", selected=False)
    view.on_change()


def force_update(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    with _batch(view.workspace):
        for src in sources:
            view.workspace.update_source(str(src["id"]), forceUpdate=True)
    QMessageBox.information(view, "Forcer MAJ", "Mise à jour forcée demandée.")
    view.on_change()
