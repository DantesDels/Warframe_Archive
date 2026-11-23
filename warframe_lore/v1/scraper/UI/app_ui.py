"""UI construction helpers for AtelierApp."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QStatusBar, QVBoxLayout, QWidget

from .actions import commands
from .execution_panel import ExecutionPanel
from .views.details import DetailPane
from .views.header import HeaderBar
from .views.sidebar import Sidebar

VERSION_LABEL = "Version v1.0.0-alpha • Mis à jour : 1h"


def build_ui(app: Any) -> None:
    central = QWidget()
    app.setCentralWidget(central)
    root = QVBoxLayout(central)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    app.header = HeaderBar()
    root.addWidget(app.header)
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)
    app.sidebar = Sidebar()
    app.details = DetailPane()
    splitter.addWidget(app.sidebar)
    splitter.addWidget(app.details)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 3)
    _bind_sidebar(app)
    app.sidebar.selection_changed.connect(app.on_select)
    app.status_bar = QStatusBar()
    app.setStatusBar(app.status_bar)
    app.execution = ExecutionPanel()
    app.execution.set_status_bar(app.status_bar)
    vertical = QSplitter(Qt.Orientation.Vertical)
    vertical.setChildrenCollapsible(False)
    vertical.addWidget(splitter)
    vertical.addWidget(app.execution)
    vertical.setStretchFactor(0, 3)
    vertical.setStretchFactor(1, 1)
    root.addWidget(vertical, 1)
    app.status_bar.addPermanentWidget(QLabel(VERSION_LABEL))


def _bind_sidebar(app: Any) -> None:
    app.sidebar.create_requested.connect(app.create_universe)
    app.sidebar.rename_requested.connect(app.rename_universe)
    app.sidebar.settings_requested.connect(lambda: commands.open_app_settings(app))
    app.sidebar.execute_requested.connect(app._execute_universe)
    app.sidebar.sync_requested.connect(app._sync_universe)
    app.sidebar.delete_requested.connect(app._delete_universe)
    app.sidebar.sync_all_requested.connect(lambda: commands.sync_all(app))
