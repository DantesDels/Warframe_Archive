"""Qt stylesheet and palette helpers for the Atelier UI."""

from __future__ import annotations

# ruff: noqa: E501

COLORS = {
    "header_bg": "#355878",
    "header_bg_alt": "#2c4a66",
    "header_text": "#ffffff",
    "sidebar_bg": "#f4f6f8",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "border": "#94a3b8",
    "border_soft": "#cbd5e1",
    "checkbox_border": "#64748b",
    "text": "#1e293b",
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
    "QMainWindow, QDialog { background: %(surface_alt)s; color: %(text)s; }",
    "QWidget { color: %(text)s; font-size: 13px; }",
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
    "QLineEdit, QSpinBox { background: %(surface)s; color: %(text)s;"
    " border: 1px solid %(border)s; border-radius: 4px; padding: 6px; }",
    "QLineEdit:focus, QSpinBox:focus { border: 1px solid %(accent)s; }",
    "QListWidget { background: %(sidebar_bg)s; border: none; color: %(text)s; }",
    "QListWidget::item:selected { background: %(selection)s; color: %(selection_text)s; }",
    "QTabWidget::pane { border: 1px solid %(border_soft)s; background: %(surface)s; }",
    "QTabBar::tab { background: #e2e8f0; color: %(text)s;"
    " border: 1px solid %(border_soft)s; border-bottom: none; padding: 6px 14px;"
    " margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }",
    "QTabBar::tab:selected { background: %(surface)s; color: %(accent)s;"
    " font-weight: 700; border-bottom: 2px solid %(accent)s; }",
    "QTabBar::tab:hover { background: %(accent_soft)s; }",
    "QTableView, QTreeView { background: %(surface)s; color: %(text)s;"
    " gridline-color: %(border_soft)s; selection-background-color: %(accent_soft)s;"
    " selection-color: %(text)s; }",
    "QTreeView::item { padding: 3px 4px; }",
    "QTreeView::item:selected, QTreeView::item:hover { background: %(accent_soft)s;"
    " color: %(text)s; }",
    "QHeaderView::section { background: #e8edf3; color: %(text)s; padding: 6px;"
    " border: none; border-bottom: 1px solid %(border_soft)s; font-weight: 600; }",
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
    "QGroupBox { font-weight: 600; border: 1px solid %(border_soft)s;"
    " border-radius: 4px; margin-top: 8px; padding-top: 8px; }",
    "QCheckBox, QDialog QLabel, QLabel { color: %(text)s; }",
    "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }",
    "QCheckBox::indicator:unchecked { background: %(surface)s;"
    " border: 1px solid %(checkbox_border)s; }",
    "QCheckBox::indicator:unchecked:hover { background: %(accent_soft)s;"
    " border-color: %(accent)s; }",
    "QCheckBox::indicator:checked { background: %(accent)s;"
    " border: 1px solid %(accent)s; }",
    "QCheckBox::indicator:disabled { background: %(bar_bg)s;"
    " border: 1px solid %(border_soft)s; }",
)


def app_stylesheet() -> str:
    """Return the global QSS for the main window and dialogs."""
    return "\n".join(rule % COLORS for rule in _STYLES)
