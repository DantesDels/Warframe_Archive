"""Dialog for assigning source trust profiles per universe."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from ....truth.trust import (
    TRUST_PROFILE_ORDER,
    infer_trust_profile,
    trust_label,
    trust_weight,
)
from ...dialogs.responsive import fit_to_screen, scrollable_dialog_body


class TrustProfilesDialog(QDialog):
    """Edit trust profiles (Official, Documentation, Wiki, Third-party)."""

    def __init__(
        self, parent: QWidget | None, workspace: Any, universe_id: str
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Profils de confiance des sources")
        self.setModal(True)
        self._workspace = workspace
        self._combos: dict[str, QComboBox] = {}
        outer, body = scrollable_dialog_body(self)
        sources = list(workspace.sources_for(universe_id))
        if not sources:
            body.addWidget(QLabel("Aucune source enregistrée pour cet Univers."))
        else:
            form = QFormLayout()
            for src in sources:
                sid = str(src.get("id", ""))
                loc = str(src.get("location", sid))
                short = loc if len(loc) <= 58 else loc[:55] + "..."
                combo = QComboBox()
                for key in TRUST_PROFILE_ORDER:
                    pct = int(round(trust_weight(key) * 100))
                    combo.addItem(f"{trust_label(key)} ({pct} %)", key)
                current = infer_trust_profile(src)
                combo.setCurrentIndex(max(0, combo.findData(current)))
                form.addRow(QLabel(short), combo)
                self._combos[sid] = combo
            body.addLayout(form)
        buttons = QDialogButtonBox()
        role = QDialogButtonBox.ButtonRole
        buttons.addButton("Enregistrer", role.AcceptRole)
        buttons.addButton("Annuler", role.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        fit_to_screen(self, ideal_width=640, ideal_height=480)

    def _save(self) -> None:
        sources = {
            str(s.get("id", "")): s
            for s in self._workspace.data.get("sources", [])
        }
        with self._workspace.batch_save():
            for sid, combo in self._combos.items():
                src = sources.get(sid)
                if src is not None:
                    src["trustProfile"] = str(combo.currentData() or "third_party")
        self.accept()
