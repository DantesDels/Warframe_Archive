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
    "text": "#1e293b",
    "muted": "#475569",
    "selection": "#1d5fa7",
    "selection_text": "#ffffff",
    "accent": "#1d4ed8",
    "accent_soft": "#dbeafe",
    "bar_bg": "#e2e8f0",
    "log_bg": "#0f172a",
    "log_text": "#e2e8f0",
    "log_muted": "#94a3b8",
}


def app_stylesheet() -> str:
    """Return the global QSS for the main window and dialogs."""
    c = COLORS
    return (
        f"QMainWindow, QDialog {{ background: {c['surface_alt']}; color: {c['text']}; }}\n"
        f"QWidget {{ color: {c['text']}; font-size: 13px; }}\n"
        f"QFrame#HeaderBar {{ background: {c['header_bg']}; }}\n"
        f"QLabel#HeaderTitle, QLabel#HeaderMeta, QLabel#HeaderSelection {{"
        f" color: {c['header_text']}; }}\n"
        f"QPushButton#HeaderButton {{ background: {c['header_bg_alt']};"
        f" color: {c['header_text']}; border: 1px solid #5b7fa3;"
        " border-radius: 4px; padding: 5px 10px; }\n"
        "QPushButton#HeaderButton:hover { background: #426c91; }\n"
        f"QFrame#Sidebar {{ background: {c['sidebar_bg']};"
        f" border-right: 1px solid {c['border_soft']}; }}\n"
        f"QPushButton#SidebarIconButton {{ background: {c['surface']}; color: {c['text']};"
        f" border: 1px solid {c['border_soft']}; border-radius: 6px; padding: 0;"
        " font-size: 14px; font-weight: 600; }\n"
        f"QPushButton#SidebarIconButton:hover {{ background: {c['accent_soft']};"
        f" border-color: {c['accent']}; color: {c['accent']}; }}\n"
        f"QLineEdit, QSpinBox {{ background: {c['surface']}; color: {c['text']};"
        f" border: 1px solid {c['border']}; border-radius: 4px; padding: 6px; }}\n"
        f"QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {c['accent']}; }}\n"
        f"QListWidget {{ background: {c['sidebar_bg']}; border: none; color: {c['text']}; }}\n"
        f"QListWidget::item:selected {{ background: {c['selection']};"
        f" color: {c['selection_text']}; }}\n"
        f"QTabWidget::pane {{ border: 1px solid {c['border_soft']};"
        f" background: {c['surface']}; }}\n"
        f"QTabBar::tab {{ background: #e2e8f0; color: {c['text']};"
        f" border: 1px solid {c['border_soft']}; border-bottom: none;"
        " padding: 6px 14px; margin-right: 2px; border-top-left-radius: 4px;"
        " border-top-right-radius: 4px; }\n"
        f"QTabBar::tab:selected {{ background: {c['surface']}; color: {c['accent']};"
        f" font-weight: 700; border-bottom: 2px solid {c['accent']}; }}\n"
        f"QTabBar::tab:hover {{ background: {c['accent_soft']}; }}\n"
        f"QTableView, QTreeView {{ background: {c['surface']}; color: {c['text']};"
        f" gridline-color: {c['border_soft']};"
        f" selection-background-color: {c['accent_soft']}; selection-color: {c['text']}; }}\n"
        "QTreeView::item { padding: 3px 4px; }\n"
        f"QTreeView::item:selected, QTreeView::item:hover {{"
        f" background: {c['accent_soft']}; color: {c['text']}; }}\n"
        f"QHeaderView::section {{ background: #e8edf3; color: {c['text']}; padding: 6px;"
        f" border: none; border-bottom: 1px solid {c['border_soft']};"
        " font-weight: 600; }\n"
        f"QStatusBar {{ background: #e8edf3; color: {c['text']};"
        f" border-top: 1px solid {c['border_soft']}; }}\n"
        f"QProgressBar {{ border: 1px solid {c['border']}; border-radius: 4px;"
        f" background: {c['bar_bg']}; color: {c['text']}; text-align: center; }}\n"
        f"QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}\n"
        f"QPlainTextEdit {{ background: {c['log_bg']}; color: {c['log_text']};"
        f" border: 1px solid {c['border']}; border-radius: 4px;"
        " font-family: Consolas, 'Courier New', monospace;"
        " padding: 6px; }\n"
        f"QPlainTextEdit#DataPreview {{ background: {c['surface']}; color: {c['text']};"
        f" border: 1px solid {c['border_soft']}; padding: 8px; }}\n"
        f"QPushButton {{ background: {c['surface']}; color: {c['text']};"
        f" border: 1px solid {c['border']}; border-radius: 4px; padding: 5px 12px; }}\n"
        f"QPushButton:hover {{ background: #e8edf3; border-color: {c['accent']}; }}\n"
        f"QGroupBox {{ font-weight: 600; border: 1px solid {c['border_soft']};"
        " border-radius: 4px; margin-top: 8px; padding-top: 8px; }\n"
        f"QCheckBox, QDialog QLabel, QLabel {{ color: {c['text']}; }}\n"
    )
