"""Action handlers for the sources tab."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
)

from ..security import validate_import


def build_actions(view: Any) -> QHBoxLayout:
    bar = QHBoxLayout()
    view._suspend_btn = QPushButton("Suspendre")
    view._suspend_btn.clicked.connect(lambda: toggle_suspend(view))
    buttons = [
        ("+ Ajouter URL", lambda: add_url(view)),
        ("+ Importer fichier", lambda: import_file(view)),
        ("+ Importer dossier", lambda: import_directory(view)),
    ]
    for label, slot in buttons:
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
    all_suspended = all(str(s.get("status")) == "suspended" for s in sources)
    status = "approved" if all_suspended else "suspended"
    for source in sources:
        view.workspace.update_source(
            str(source["id"]),
            status=status,
            selected=status == "approved",
        )
    view.on_change()


def edit_source(view: Any) -> None:
    source = cast(dict[str, Any] | None, view.current_source())
    if not source:
        return
    value, ok = QInputDialog.getText(
        view,
        "Modifier la source",
        "Emplacement :",
        text=str(source.get("location", "")),
    )
    if ok and value.strip():
        view.workspace.update_source(str(source["id"]), location=value.strip())
        view.on_change()


def delete_source(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    question = "Supprimer la source sélectionnée ?"
    if len(sources) > 1:
        question = f"Supprimer les {len(sources)} sources sélectionnées ?"
    if (
        QMessageBox.question(view, "Suppression", question)
        == QMessageBox.StandardButton.Yes
    ):
        for source in sources:
            view.workspace.delete_source(str(source["id"]))
        view.on_change()


def blacklist_source(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    for source in sources:
        view.workspace.update_source(
            str(source["id"]), status="blacklisted", selected=False
        )
    view.on_change()


def force_update(view: Any) -> None:
    sources = cast(list[dict[str, Any]], view.selected_sources())
    if not sources:
        return
    for source in sources:
        view.workspace.update_source(str(source["id"]), forceUpdate=True)
    QMessageBox.information(view, "Forcer MAJ", "Mise à jour forcée demandée.")
    view.on_change()
