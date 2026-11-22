"""Qt stylesheet and palette helpers for the Atelier UI."""

from __future__ import annotations

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
    "accent": "#9dbcff",
    "bar_bg": "#e2e8f0",
    "log_bg": "#0f172a",
    "log_text": "#e2e8f0",
}


def app_stylesheet() -> str:
    """Return the global QSS for the main window and dialogs."""
    c = COLORS
    return (
        "QMainWindow, QDialog {"
        f" background: {c['surface_alt']}; color: {c['text']}; }}\n"
        f"QWidget {{ color: {c['text']}; font-size: 13px; }}\n"
        f"QFrame#HeaderBar {{ background: {c['header_bg']}; }}\n"
        "QLabel#HeaderTitle {"
        f" color: {c['header_text']}; font-weight: 700; font-size: 14px; }}\n"
        "QLabel#HeaderMeta, QLabel#HeaderSelection {"
        f" color: {c['header_text']}; font-weight: 500; }}\n"
        "QPushButton#HeaderButton {\n"
        f"  background: {c['header_bg_alt']}; color: {c['header_text']};\n"
        "  border: 1px solid #5b7fa3; border-radius: 4px;\n"
        "  padding: 5px 10px; font-weight: 500;\n}\n"
        "QPushButton#HeaderButton:hover { background: #426c91; }\n"
        f"QFrame#Sidebar {{ background: {c['sidebar_bg']};"
        f" border-right: 1px solid {c['border_soft']}; }}\n"
        "QPushButton#SidebarIconButton {\n"
        f"  background: {c['surface']}; color: {c['text']};\n"
        f"  border: 1px solid {c['border_soft']}; border-radius: 6px;\n"
        "  padding: 0; font-size: 14px; font-weight: 600;\n"
        "  font-family: 'Segoe UI Symbol','Segoe UI','Arial';\n}\n"
        "QPushButton#SidebarIconButton:hover {\n"
        f"  background: #dbeafe; border-color: {c['accent']};\n"
        f"  color: {c['accent']};\n}}\n"
        "QPushButton#SidebarIconButton:pressed { background: #bfdbfe; }\n"
        "QLineEdit, QSpinBox {\n"
        f"  background: {c['surface']}; color: {c['text']};\n"
        f"  border: 1px solid {c['border']}; border-radius: 4px; padding: 6px;\n}}\n"
        f"QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {c['accent']}; }}\n"
        f"QListWidget {{ background: {c['sidebar_bg']}; border: none;"
        f" outline: 0; color: {c['text']}; }}\n"
        "QListWidget:focus { border: none; outline: 0; }\n"
        "QListWidget::item { padding: 2px; border: none; border-radius: 4px; }\n"
        "QListWidget::item:focus { border: none; outline: none; }\n"
        f"QListWidget::item:selected {{ background: {c['selection']};"
        f" color: {c['selection_text']}; border: none; outline: none; }}\n"
        f"QTabWidget::pane {{ border: 1px solid {c['border_soft']};"
        f" background: {c['surface']}; }}\n"
        "QTabBar::tab {\n"
        f"  background: #e2e8f0; color: {c['muted']};\n"
        f"  border: 1px solid {c['border_soft']}; border-bottom: none;\n"
        "  padding: 6px 14px; margin-right: 2px; border-top-left-radius: 4px;\n"
        "  border-top-right-radius: 4px;\n}\n"
        f"QTabBar::tab:selected {{ background: {c['surface']};"
        f" color: {c['accent']}; font-weight: 600; }}\n"
        f"QTableView {{ background: {c['surface']}; color: {c['text']};"
        f" gridline-color: {c['border_soft']};\n"
        f"  selection-background-color: #ffffff; selection-color: {c['text']}; }}\n"
        f"QTreeView::item:selected {{ background: #ffffff; color: {c['text']}; }}\n"
        "QHeaderView::section {\n"
        f"  background: #e8edf3; color: {c['text']}; padding: 6px;\n"
        f"  border: none; border-bottom: 1px solid {c['border_soft']};\n"
        "  font-weight: 600;\n}\n"
        f"QStatusBar {{ background: #e8edf3; color: {c['text']};"
        f" border-top: 1px solid {c['border_soft']}; }}\n"
        "QProgressBar {\n"
        f"  border: 1px solid {c['border']}; border-radius: 4px;\n"
        f"  background: {c['bar_bg']}; color: {c['text']}; text-align: center;\n}}\n"
        f"QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}\n"
        f"QPlainTextEdit {{ background: {c['log_bg']}; color: {c['log_text']};"
        f" border: 1px solid {c['border']}; border-radius: 4px;\n"
        "  font-family: Consolas, 'Courier New', monospace; padding: 4px; }\n"
        "QPushButton {\n"
        f"  background: {c['surface']}; color: {c['text']};\n"
        f"  border: 1px solid {c['border']}; border-radius: 4px;\n"
        "  padding: 5px 12px;\n}\n"
        f"QPushButton:hover {{ background: #e8edf3; border-color: {c['accent']}; }}\n"
        f"QPushButton:pressed {{ background: #dbe7f3; }}\n"
        f"QGroupBox {{ font-weight: 600; border: 1px solid {c['border_soft']};\n"
        "  border-radius: 4px; margin-top: 8px; padding-top: 8px; }\n"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }\n"
        f"QCheckBox {{ color: {c['text']}; spacing: 6px; }}\n"
        f"QDialog QLabel, QLabel {{ color: {c['text']}; }}\n"
    )
