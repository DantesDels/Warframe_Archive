"""Reusable read-only table widget for the detail tabs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def add_table(
    parent: tk.Misc,
    columns: list[tuple],
    rows: list[tuple],
) -> ttk.Treeview:
    """Build a scrollable, read-only table and return it.

    Column spec: (key, label) or (key, label, width, stretch).
    """
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    keys = [col[0] for col in columns]
    table = ttk.Treeview(frame, columns=keys, show="headings")
    for col in columns:
        key, label = col[0], col[1]
        width = col[2] if len(col) > 2 else 150
        stretch = col[3] if len(col) > 3 else True
        table.heading(key, text=label)
        table.column(key, width=width, anchor="w", stretch=stretch)
    ybar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    xbar = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
    table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    ybar.pack(in_=frame, side="right", fill="y")
    table.pack(in_=frame, side="left", fill="both", expand=True)
    xbar.pack(fill="x")
    info = ttk.Label(parent, foreground="#68738a")
    info.pack(fill="x", pady=(2, 0))
    table.bind(
        "<<TreeviewSelect>>",
        lambda _e: _show_info(table, columns, info),
    )
    for row in rows:
        table.insert("", "end", values=row)
    table._info_label = info  # type: ignore[attr-defined]
    return table


def _show_info(table: ttk.Treeview, columns: list[tuple], label: ttk.Label) -> None:
    selection = table.selection()
    if not selection:
        label.configure(text="")
        return
    values = table.item(selection[0], "values")
    parts = [f"{columns[i][1]} : {values[i]}" for i in range(len(values))]
    label.configure(text="  |  ".join(parts[:2]))

