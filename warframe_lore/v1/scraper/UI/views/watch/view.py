"""Veille tab: conditional watchers (ETag/Last-Modified) and targeted delta."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....capabilities.models import UniverseCapabilities
from ....watch import infer_watcher_kind, watch_url_for
from ..simple_table import SimpleTable
from .worker import WatchWorker

_WATCH_KIND_LABELS = {
    "rss": "RSS / Atom",
    "sitemap": "Sitemap XML",
    "github_release": "Release GitHub",
    "changelog": "Changelog / Page",
    "api": "API JSON",
}
_HEADERS = ["Source surveillée", "Type veille", "Dernier contrôle", "État", "Détail"]
_WIDTHS = {1: 115, 2: 135, 3: 95, 4: 200}


def watch_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build the conditional watching and delta update tab for one universe."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    uid = str(universe.get("id", ""))
    caps = UniverseCapabilities.from_dict(workspace.capabilities_for(uid))

    bar = QHBoxLayout()
    bar.setSpacing(8)
    enabled_cb = QCheckBox("Veille automatique")
    enabled_cb.setObjectName("WatchEnabledCheck")
    enabled_cb.setChecked(caps.watch.enabled)
    poll_spin = QSpinBox()
    poll_spin.setObjectName("WatchPollMinutes")
    poll_spin.setRange(1, 1440)
    poll_spin.setSuffix(" min")
    poll_spin.setValue(max(1, caps.watch.poll_minutes))
    check_btn = QPushButton("Vérifier maintenant")
    check_btn.setObjectName("WatchCheckNowButton")
    delta_btn = QPushButton("Delta sur changements")
    delta_btn.setObjectName("WatchRunDeltaButton")
    for w in (enabled_cb, QLabel("Intervalle :"), poll_spin, check_btn, delta_btn):
        bar.addWidget(w)
    bar.addStretch(1)

    table = SimpleTable(
        _HEADERS, stretch_columns=[0], elide_first=True,
        left_columns={0, 4}, column_widths=_WIDTHS,
    )
    rows, ids, changed_ids = _rows_for(workspace, uid)
    table.set_rows(rows, ids)
    delta_btn.setEnabled(bool(changed_ids))
    status = QLabel(_summary_text(len(rows), len(changed_ids)))
    status.setObjectName("CandidateDetail")
    workers: list[WatchWorker] = []

    def _save_cfg() -> None:
        cfg = UniverseCapabilities.from_dict(workspace.capabilities_for(uid))
        cfg.watch.enabled = enabled_cb.isChecked()
        cfg.watch.poll_minutes = poll_spin.value()
        workspace.set_capabilities(uid, cfg.to_dict())

    def _launch(delta_targets: list[str] | None = None) -> None:
        check_btn.setEnabled(False)
        delta_btn.setEnabled(False)
        status.setText(
            "Delta ciblé en cours..."
            if delta_targets is not None
            else "Vérification conditionnelle (ETag / Last-Modified) en cours..."
        )
        worker = WatchWorker(workspace, uid, delta_ids=delta_targets)
        workers.append(worker)

        def _done(payload: object) -> None:
            kind, data = payload if isinstance(payload, tuple) else ("error", payload)
            check_btn.setEnabled(True)
            if kind == "error":
                status.setText(f"Erreur veille : {data}")
                return
            on_change()

        worker.finished_report.connect(_done)
        worker.start()

    enabled_cb.toggled.connect(lambda _c: _save_cfg())
    poll_spin.valueChanged.connect(lambda _v: _save_cfg())
    check_btn.clicked.connect(lambda: _launch(None))
    delta_btn.clicked.connect(lambda: _launch(changed_ids))
    layout.addLayout(bar)
    layout.addWidget(table, 1)
    layout.addWidget(status)
    widget._watch_workers = workers  # type: ignore[attr-defined]
    return widget


def _rows_for(
    workspace: Any, uid: str
) -> tuple[list[list[str]], list[str], list[str]]:
    rows, ids, changed = [], [], []
    for src in workspace.sources_for(uid):
        if not str(src.get("location", "")).strip().startswith(("http://", "https://")):
            continue
        sid = str(src.get("id", ""))
        wkind = infer_watcher_kind(src)
        st = src.get("watch_state") if isinstance(src.get("watch_state"), dict) else {}
        is_mod = bool(st.get("last_changed", False))
        if is_mod:
            changed.append(sid)
        ts = str(st.get("last_checked_at", "")).replace("T", " ").rstrip("Z") or "—"
        checked_ok = bool(st.get("last_checked_at"))
        lbl = "Modifié" if is_mod else ("OK" if checked_ok else "Attente")
        rows.append([
            watch_url_for(src, wkind), _WATCH_KIND_LABELS.get(wkind, wkind),
            ts, lbl, str(st.get("last_reason", "Jamais vérifié")),
        ])
        ids.append(sid)
    return rows, ids, changed


def _summary_text(total: int, changed: int) -> str:
    return (
        f"{total} source(s) surveillable(s) · {changed} changement(s) en attente. "
        "Utilise ETag / Last-Modified (304) pour éviter les téléchargements inutiles."
    )
