"""Language selector bar and background cleanup of off-language/off-topic entries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ....collect.language import DEFAULT_ALLOWED_LANGUAGES, SUPPORTED_LANGUAGES
from ....collect.language_purge import (
    purge_disallowed_languages_and_duplicates,
    scan_disallowed_and_off_topic,
    set_universe_allowed_languages,
    universe_allowed_languages,
)
from ...runtime.main_thread_bridge import MainThreadBridge
from ...runtime.work_launcher import WorkLauncher

__all__ = [
    "build_language_selector_bar",
    "confirm_and_cleanup_universe",
    "purge_disallowed_languages_and_duplicates",
    "scan_disallowed_and_off_topic",
    "set_universe_allowed_languages",
    "universe_allowed_languages",
]


class _CleanupWorker(QObject):
    finished = Signal(object)

    def __init__(self, workspace: Any, uid: str, langs: tuple[str, ...]) -> None:
        super().__init__()
        self.workspace, self.uid, self.langs = workspace, uid, langs

    def run(self) -> None:
        rem_s, rem_c = purge_disallowed_languages_and_duplicates(
            self.workspace, self.uid, self.langs
        )
        self.finished.emit((rem_s, rem_c))


def confirm_and_cleanup_universe(
    parent: QWidget, workspace: Any, universe_id: str,
    langs: tuple[str, ...], on_change: Callable[[], None],
) -> None:
    """Scan off-language/off-topic entries, ask confirmation and purge in background."""
    _, _, rem_s, rem_c = scan_disallowed_and_off_topic(workspace, universe_id, langs)
    total = rem_s + rem_c
    lang_str = ", ".join(c.upper() for c in langs)
    title = "Nettoyer hors-langue / hors-sujet"
    if total == 0:
        QMessageBox.information(
            parent, title, f"Aucun élément hors-langue ou hors-sujet ({lang_str})."
        )
        return
    msg = (
        f"{total} élément(s) hors-langue ou hors-sujet détecté(s) "
        f"({rem_s} source(s), {rem_c} candidat(s)).\n\n"
        f"Langues autorisées : {lang_str}\nSupprimer ces éléments maintenant ?"
    )
    btns = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    if QMessageBox.question(parent, title, msg, btns) != QMessageBox.StandardButton.Yes:
        return
    thread = QThread(parent)
    worker = _CleanupWorker(workspace, universe_id, langs)
    launcher = WorkLauncher()
    worker.moveToThread(thread)
    launcher.requested.connect(worker.run, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(launcher.launch)

    def _done(payload: Any) -> None:
        rs, rc = payload
        thread.quit()
        thread.wait(1000)
        on_change()
        QMessageBox.information(
            parent, title,
            f"{rs + rc} élément(s) supprimé(s) ({rs} source(s), {rc} candidat(s)).",
        )

    bridge = MainThreadBridge(_done)
    worker.finished.connect(bridge.on_value, Qt.ConnectionType.QueuedConnection)
    parent._cleanup_refs = (thread, worker, launcher, bridge)  # type: ignore[attr-defined]
    thread.start()


def build_language_selector_bar(
    parent: QWidget, workspace: Any, universe: dict[str, Any],
    on_filter_changed: Callable[[tuple[str, ...]], None],
    on_change: Callable[[], None],
) -> tuple[QHBoxLayout, Callable[[], tuple[str, ...]]]:
    """Build the language checkbox bar and one-click cleanup button."""
    uid = str(universe.get("id", ""))
    active_langs = set(universe_allowed_languages(workspace, uid))
    bar = QHBoxLayout(spacing=4)
    bar.addWidget(QLabel("Langues :", objectName="MutedHint"))
    checks = {
        c: QCheckBox(t, objectName=f"CandidateLang_{c}", checked=c in active_langs)
        for c, t in SUPPORTED_LANGUAGES
    }
    for cb in checks.values():
        bar.addWidget(cb)

    def current_langs() -> tuple[str, ...]:
        chosen = [code for code, cb in checks.items() if cb.isChecked()]
        return tuple(chosen) if chosen else DEFAULT_ALLOWED_LANGUAGES

    def _on_toggled() -> None:
        langs = set_universe_allowed_languages(workspace, uid, current_langs())
        if not any(cb.isChecked() for cb in checks.values()) and "en" in checks:
            checks["en"].blockSignals(True)
            checks["en"].setChecked(True)
            checks["en"].blockSignals(False)
        on_filter_changed(langs)

    for cb in checks.values():
        cb.toggled.connect(lambda _checked: _on_toggled())

    en_only_btn = QPushButton("EN uniquement", objectName="CandidatesEnOnlyButton")

    def _select_en_only() -> None:
        for code, cb in checks.items():
            cb.blockSignals(True)
            cb.setChecked(code == "en")
            cb.blockSignals(False)
        _on_toggled()

    en_only_btn.clicked.connect(_select_en_only)
    purge_btn = QPushButton(
        "Nettoyer hors-langue / hors-sujet", objectName="PurgeForeignCandidatesButton"
    )
    purge_btn.clicked.connect(
        lambda: confirm_and_cleanup_universe(
            parent, workspace, uid,
            set_universe_allowed_languages(workspace, uid, current_langs()), on_change,
        )
    )
    bar.addWidget(en_only_btn)
    bar.addWidget(purge_btn)
    bar.addStretch(1)
    return bar, current_langs
