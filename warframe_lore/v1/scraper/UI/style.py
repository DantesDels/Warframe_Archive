"""Qt stylesheet and light palette helpers for high-contrast Atelier UI."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

# ruff: noqa: E501

COLORS = {
    "header_bg": "#355878",
    "header_bg_alt": "#2c4a66",
    "header_text": "#ffffff",
    "sidebar_bg": "#f4f6f8",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "row_alt": "#f1f5f9",
    "border": "#94a3b8",
    "border_soft": "#cbd5e1",
    "checkbox_border": "#64748b",
    "text": "#0f172a",
    "muted": "#475569",
    "selection": "#1d5fa7",
    "selection_text": "#ffffff",
    "accent": "#1d4ed8",
    "accent_soft": "#dbeafe",
    "bar_bg": "#e2e8f0",
    "progress_track": "#334155",
    "log_bg": "#0f172a",
    "log_text": "#e2e8f0",
    "log_muted": "#94a3b8",
}

_STYLES = (
    "QMainWindow, QDialog, QMessageBox { background: %(surface_alt)s; color: %(text)s; }",
    "QWidget { color: %(text)s; font-size: 13px; }",
    "QScrollArea, QScrollArea > QWidget > QWidget, QWidget#ScrollContent {"
    " background: %(surface_alt)s; color: %(text)s; }",
    "QFrame#HeaderBar { background: %(header_bg)s; }",
    "QLabel#HeaderTitle, QLabel#HeaderMeta, QLabel#HeaderSelection { color: %(header_text)s; }",
    "QPushButton#HeaderButton { background: %(header_bg_alt)s; color: %(header_text)s;"
    " border: 1px solid #5b7fa3; border-radius: 4px; padding: 5px 10px; }",
    "QPushButton#HeaderButton:hover { background: #426c91; }",
    "QPushButton#HeaderButton:pressed { background: #24405a;"
    " border-color: #9fc2e0; padding-top: 6px; padding-bottom: 4px; }",
    "QFrame#Sidebar { background: %(sidebar_bg)s; border-right: 1px solid %(border_soft)s; }",
    "QPushButton#SidebarIconButton { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border_soft)s; border-radius: 6px; padding: 0;"
    " font-size: 14px; font-weight: 600; }",
    "QPushButton#SidebarIconButton:hover { background: %(accent_soft)s;"
    " border-color: %(accent)s; color: %(accent)s; }",
    "QPushButton#SidebarIconButton:pressed { background: #93c5fd;"
    " border-color: #1e40af; padding-top: 1px; }",
    "QLineEdit, QSpinBox, QComboBox { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border)s; border-radius: 4px; padding: 5px 8px; min-height: 20px; }",
    "QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid %(accent)s; }",
    "QComboBox::drop-down { border: none; width: 22px; }",
    "QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border)s; selection-background-color: %(accent_soft)s;"
    " selection-color: %(text)s; outline: 0; }",
    "QSpinBox::up-button, QSpinBox::down-button { background: %(row_alt)s;"
    " border-left: 1px solid %(border_soft)s; width: 18px; }",
    "QListWidget { background: %(sidebar_bg)s; border: none; color: %(text)s; }",
    "QListWidget::item:selected { background: %(selection)s; color: %(selection_text)s; }",
    "QTabWidget::pane { border: 1px solid %(border_soft)s; background: %(surface)s; }",
    "QTabBar::tab { background: %(bar_bg)s; color: %(text)s;"
    " border: 1px solid %(border_soft)s; border-bottom: none; padding: 6px 9px;"
    " margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }",
    "QTabBar::tab:selected { background: %(surface)s; color: %(accent)s;"
    " font-weight: 700; border-bottom: 2px solid %(accent)s; }",
    "QTabBar::tab:hover { background: %(accent_soft)s; }",
    "QTableView, QTreeView { background: %(surface)s; alternate-background-color: %(row_alt)s;"
    " color: %(text)s; gridline-color: %(border_soft)s;"
    " selection-background-color: %(accent_soft)s; selection-color: %(text)s; }",
    "QTableView::item { padding: 4px 6px; }",
    "QTableView::item:selected { background: %(accent_soft)s; color: %(text)s; }",
    "QTreeView::item { padding: 3px 4px; }",
    "QTreeView::item:selected, QTreeView::item:hover { background: %(accent_soft)s;"
    " color: %(text)s; }",
    "QHeaderView::section { background: #e8edf3; color: %(text)s; padding: 6px 8px;"
    " border: none; border-right: 1px solid %(border_soft)s;"
    " border-bottom: 1px solid %(border)s; font-weight: 600; }",
    "QHeaderView::section:hover { background: %(accent_soft)s; }",
    "QStatusBar { background: #e8edf3; color: %(text)s;"
    " border-top: 1px solid %(border_soft)s; }",
    "QProgressBar { background: %(progress_track)s; color: %(header_text)s;"
    " font-weight: 700; text-align: center; min-height: 18px;"
    " border: 1px solid %(checkbox_border)s; border-radius: 4px; }",
    "QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }",
    "QPlainTextEdit { background: %(log_bg)s; color: %(log_text)s;"
    " border: 1px solid %(border)s; border-radius: 4px;"
    " font-family: Consolas, 'Courier New', monospace; padding: 6px; }",
    "QPlainTextEdit#DataPreview { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border_soft)s; padding: 8px; }",
    "QPushButton { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border)s; border-radius: 4px; padding: 5px 12px; }",
    "QPushButton:hover { background: #e8edf3; border-color: %(accent)s; }",
    "QPushButton:pressed { background: #bfdbfe; border-color: #1e40af;"
    " padding-top: 6px; padding-bottom: 4px; }",
    "QPushButton:focus { border-color: #1e40af; outline: 1px solid #1e40af; }",
    "QPushButton:disabled { background: %(bar_bg)s; color: #94a3b8;"
    " border-color: #cbd5e1; }",
    "QPushButton#DangerButton { background: #fef2f2; color: #b91c1c;"
    " border: 1px solid #fca5a5; border-radius: 4px; padding: 5px 12px; font-weight: 600; }",
    "QPushButton#DangerButton:hover { background: #fee2e2; border-color: #dc2626; }",
    "QPushButton#TagChip { background: %(accent_soft)s; color: #1e3a8a;"
    " border: 1px solid #93c5fd; border-radius: 11px; padding: 3px 10px;"
    " font-size: 12px; font-weight: 600; }",
    "QPushButton#TagChip:hover { background: #fee2e2; color: #991b1b; border-color: #f87171; }",
    "QGroupBox { background: %(surface)s; color: %(text)s; font-weight: 600;"
    " border: 1px solid %(border_soft)s; border-radius: 6px;"
    " margin-top: 12px; padding: 12px 10px 8px 10px; }",
    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px;"
    " background: %(surface_alt)s; color: %(text)s; font-weight: 700; }",
    "QCheckBox, QDialog QLabel, QLabel { background: transparent; color: %(text)s; }",
    "QLabel#MutedHint { color: %(muted)s; font-size: 12px; }",
    "QLabel#CandidateDetail { background: %(row_alt)s; color: %(text)s;"
    " border: 1px solid %(border_soft)s; border-radius: 4px; padding: 6px 8px; font-size: 12px; }",
    "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }",
    "QCheckBox::indicator:unchecked { background: %(surface)s;"
    " border: 1px solid %(checkbox_border)s; }",
    "QCheckBox::indicator:unchecked:hover { background: %(accent_soft)s;"
    " border-color: %(accent)s; }",
    "QCheckBox::indicator:checked { background: %(accent)s;"
    " border: 1px solid %(accent)s; }",
    "QCheckBox::indicator:disabled { background: %(bar_bg)s;"
    " border: 1px solid %(border_soft)s; }",
    "QToolTip { background: %(log_bg)s; color: %(log_text)s;"
    " border: 1px solid #334155; padding: 4px 6px; }",
    "QScrollBar:vertical { background: %(bar_bg)s; width: 10px; border-radius: 5px; }",
    "QScrollBar::handle:vertical { background: %(border)s; min-height: 24px; border-radius: 5px; }",
    "QScrollBar::handle:vertical:hover { background: %(checkbox_border)s; }",
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }",
    "QScrollBar:horizontal { background: %(bar_bg)s; height: 10px; border-radius: 5px; }",
    "QScrollBar::handle:horizontal { background: %(border)s; min-width: 24px; border-radius: 5px; }",
    "QScrollBar::handle:horizontal:hover { background: %(checkbox_border)s; }",
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }",
)


def light_palette() -> QPalette:
    """Build an explicit high-contrast light QPalette immune to OS dark-mode bleed."""
    palette = QPalette()
    roles = QPalette.ColorRole
    mapping = (
        (roles.Window, COLORS["surface_alt"]),
        (roles.WindowText, COLORS["text"]),
        (roles.Base, COLORS["surface"]),
        (roles.AlternateBase, COLORS["row_alt"]),
        (roles.Text, COLORS["text"]),
        (roles.Button, COLORS["surface"]),
        (roles.ButtonText, COLORS["text"]),
        (roles.Highlight, COLORS["selection"]),
        (roles.HighlightedText, COLORS["selection_text"]),
        (roles.PlaceholderText, COLORS["muted"]),
        (roles.ToolTipBase, COLORS["log_bg"]),
        (roles.ToolTipText, COLORS["log_text"]),
    )
    for role, color in mapping:
        palette.setColor(role, QColor(color))
    return palette


def app_stylesheet() -> str:
    """Return the global QSS for the main window and dialogs."""
    return "\n".join(rule % COLORS for rule in _STYLES)


def apply_theme(target: QWidget | None = None) -> None:
    """Apply the light palette and stylesheet to QApplication and an optional widget."""
    css = app_stylesheet()
    palette = light_palette()
    qt_app = QApplication.instance()
    if isinstance(qt_app, QApplication):
        qt_app.setStyle("Fusion")
        qt_app.setPalette(palette)
        if qt_app.styleSheet() != css:
            qt_app.setStyleSheet(css)
    if target is not None:
        target.setPalette(palette)
        target.setStyleSheet(css)
