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
    QVBoxLayout,
)

from ..security import validate_import
from .candidates.language_selector import (
    confirm_and_cleanup_universe,
    universe_allowed_languages,
)


def _batch(workspace: Any) -> Any:
    return workspace.batch_save() if hasattr(workspace, "batch_save") else nullcontext()


def build_actions(view: Any) -> QVBoxLayout:
    box = QVBoxLayout(spacing=4)
    top, bottom = QHBoxLayout(spacing=6), QHBoxLayout(spacing=6)
    view._suspend_btn = QPushButton("Suspendre")
    view._suspend_btn.clicked.connect(lambda: toggle_suspend(view))
    for label, slot in (
        ("+ Ajouter URL", lambda: add_url(view)),
        ("+ Importer fichier", lambda: import_file(view)),
        ("+ Importer dossier", lambda: import_directory(view)),
        ("Nettoyer hors-langue / hors-sujet", lambda: purge_sources_languages(view)),
    ):
        btn = QPushButton(label)
        btn.clicked.connect(slot)
        top.addWidget(btn)
    top.addStretch(1)
    bottom.addWidget(view._suspend_btn)
    for label, slot in (
        ("Modifier", lambda: edit_source(view)),
        ("Supprimer", lambda: delete_source(view)),
        ("Blacklister", lambda: blacklist_source(view)),
        ("Forcer MAJ", lambda: force_update(view)),
    ):
        button = QPushButton(label)
        button.clicked.connect(slot)
        bottom.addWidget(button)
    bottom.addStretch(1)
    box.addLayout(top)
    box.addLayout(bottom)
    return box


def purge_sources_languages(view: Any) -> None:
    """Scan and remove off-language and off-topic entries for the universe."""
    uid = str(view.universe.get("id", ""))
    confirm_and_cleanup_universe(
        view, view.workspace, uid,
        universe_allowed_languages(view.workspace, uid), view.on_change,
    )


def add_url(view: Any) -> None:
    value, ok = QInputDialog.getText(view, "Ajouter une URL", "URL de la source :")
    if ok and value.strip():
        _add_location(view, value.strip(), "website")


def import_file(view: Any) -> None:
    if path := QFileDialog.getOpenFileName(view, "Importer un fichier")[0]:
        _add_location(view, path, "document")


def import_directory(view: Any) -> None:
    """Add a local directory as a recursive structured-document source."""
    if path := QFileDialog.getExistingDirectory(view, "Importer un dossier"):
        _add_location(view, path, "local_directory")


def _add_location(view: Any, location: str, kind: str) -> None:
    allowed, reason = validate_import(location)
    if not allowed:
        QMessageBox.critical(view, "Sécurité à l'import", reason)
        return
    view.workspace.add_manual_source(str(view.universe["id"]), location, kind=kind)
    view.on_change()


def toggle_suspend(view: Any) -> None:
    if not (sources := cast(list[dict[str, Any]], view.selected_sources())):
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
    if not (source := cast(dict[str, Any] | None, view.current_source())):
        return
    loc = str(source.get("location", ""))
    value, ok = QInputDialog.getText(view, "Modifier", "Emplacement :", text=loc)
    if ok and value.strip():
        view.workspace.update_source(str(source["id"]), location=value.strip())
        view.on_change()


def delete_source(view: Any) -> None:
    if not (sources := cast(list[dict[str, Any]], view.selected_sources())):
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
    if not (sources := cast(list[dict[str, Any]], view.selected_sources())):
        return
    with _batch(view.workspace):
        for src in sources:
            view.workspace.update_source(
                str(src["id"]), status="blacklisted", selected=False
            )
    view.on_change()


def force_update(view: Any) -> None:
    if sources := cast(list[dict[str, Any]], view.selected_sources()):
        with _batch(view.workspace):
            for src in sources:
                view.workspace.update_source(str(src["id"]), forceUpdate=True)
        QMessageBox.information(view, "Forcer MAJ", "Mise à jour forcée demandée.")
        view.on_change()
