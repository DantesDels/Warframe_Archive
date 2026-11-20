"""Tk/ttk theme and reusable tooltip helper."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg": "#f4f6fb",
    "surface": "#ffffff",
    "panel": "#eef2f8",
    "border": "#d7deea",
    "text": "#172033",
    "muted": "#68738a",
    "accent": "#3457d5",
    "accent_hover": "#2747b8",
}


def apply_theme(root: tk.Misc) -> None:
    """Apply a clean, modern ttk style to the application."""
    style = ttk.Style(root)
    for theme in ("clam", "vista", "xpnative"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break
    root.configure(background=PALETTE["bg"])
    style.configure(".", background=PALETTE["bg"], foreground=PALETTE["text"])
    style.configure("TFrame", background=PALETTE["bg"])
    style.configure("Surface.TFrame", background=PALETTE["surface"])
    style.configure("Panel.TFrame", background=PALETTE["panel"])
    style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"])
    style.configure(
        "Muted.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"],
    )
    style.configure(
        "Heading.TLabel", font=("Segoe UI", 16, "bold"), foreground=PALETTE["text"],
    )
    style.configure("TButton", padding=(10, 5))
    style.configure(
        "Accent.TButton", foreground="#ffffff", background=PALETTE["accent"],
    )
    style.map(
        "Accent.TButton",
        background=[
            ("active", PALETTE["accent_hover"]),
            ("!disabled", PALETTE["accent"]),
        ],
    )
    style.configure(
        "Treeview",
        background=PALETTE["surface"],
        fieldbackground=PALETTE["surface"],
        rowheight=26,
    )
    style.configure("TNotebook", background=PALETTE["bg"])
    style.configure("TNotebook.Tab", padding=(10, 5))
    style.configure(
        "Horizontal.TProgressbar", troughcolor=PALETTE["panel"], thickness=14,
    )


class Tooltip:
    """Small hover tooltip for ttk/tk widgets."""

    def __init__(self, widget: tk.Misc, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event: tk.Event) -> None:
        if self.tip or not self.text:
            return
        x_pos = self.widget.winfo_rootx() + 12
        y_pos = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x_pos}+{y_pos}")
        label = tk.Label(
            self.tip,
            text=self.text,
            background="#172033",
            foreground="#ffffff",
            padx=8,
            pady=4,
            justify="left",
        )
        label.pack()

    def _hide(self, _event: tk.Event) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None
