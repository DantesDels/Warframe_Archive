"""Action handlers for the sources tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
)

from ..security import validate_import


def build_actions(view) -> QHBoxLayout:
    bar = QHBoxLayout()
    view._suspend_btn = QPushButton("Suspendre")
    view._suspend_btn.clicked.connect(lambda: toggle_suspend(view))
    buttons = [
        ("+ Ajouter URL", lambda: add_url(view)),
        ("+ Importer fichier", lambda: import_file(view)),
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


def add_url(view) -> None:
    value, ok = QInputDialog.getText(view, "Ajouter une URL", "URL de la source :")
    if ok and value.strip():
        _add_location(view, value.strip(), "website")


def import_file(view) -> None:
    path, _ = QFileDialog.getOpenFileName(view, "Importer un fichier")
    if path:
        _add_location(view, path, "document")


def _add_location(view, location: str, kind: str) -> None:
    allowed, reason = validate_import(location)
    if not allowed:
        QMessageBox.critical(view, "S?curit? ? l'import", reason)
        return
    view.workspace.add_manual_source(view.universe["id"], location, kind=kind)
    view.on_change()


def toggle_suspend(view) -> None:
    sources = view.selected_sources()
    if not sources:
        return
    all_suspended = all(s.get("status") == "suspended" for s in sources)
    status = "approved" if all_suspended else "suspended"
    for source in sources:
        view.workspace.update_source(
            source["id"], status=status, selected=status == "approved",
        )
    view.on_change()


def edit_source(view) -> None:
    source = view.current_source()
    if not source:
        return
    value, ok = QInputDialog.getText(
        view, "Modifier la source", "Emplacement :", text=source["location"],
    )
    if ok and value.strip():
        view.workspace.update_source(source["id"], location=value.strip())
        view.on_change()


def delete_source(view) -> None:
    sources = view.selected_sources()
    if not sources:
        return
    question = "Supprimer la source s?lectionn?e ?"
    if len(sources) > 1:
        question = f"Supprimer les {len(sources)} sources s?lectionn?es ?"
    if QMessageBox.question(view, "Suppression", question) == QMessageBox.Yes:
        for source in sources:
            view.workspace.delete_source(source["id"])
        view.on_change()


def blacklist_source(view) -> None:
    sources = view.selected_sources()
    if not sources:
        return
    for source in sources:
        view.workspace.update_source(source["id"], status="blacklisted", selected=False)
    view.on_change()


def force_update(view) -> None:
    sources = view.selected_sources()
    if not sources:
        return
    for source in sources:
        view.workspace.update_source(source["id"], forceUpdate=True)
    QMessageBox.information(view, "Forcer MAJ", "Mise ? jour forc?e demand?e.")
    view.on_change()
