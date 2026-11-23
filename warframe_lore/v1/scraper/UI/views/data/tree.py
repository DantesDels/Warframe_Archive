"""Safe file-tree construction and readable previews for the Data tab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

TEXT_SUFFIXES = frozenset({
    ".md", ".txt", ".json", ".jsonl", ".csv", ".sql", ".xml", ".log",
    ".dialogue", ".yaml", ".yml", ".toml", ".ini",
})
MAX_DEPTH = 8
MAX_ENTRIES = 2000
PREVIEW_LIMIT = 200_000


def data_roots(workspace: Any, universe_id: str) -> list[Path]:
    """Return export and linked local-corpus roots for one universe."""
    workspace_path = getattr(workspace, "path", None)
    base = (
        workspace_path.parent if isinstance(workspace_path, Path)
        else Path("data/v1")
    )
    roots = [base / "exports" / universe_id]
    sources = (
        workspace.sources_for(universe_id)
        if hasattr(workspace, "sources_for") else []
    )
    for source in sources:
        if str(source.get("kind") or "") != "local_directory":
            continue
        path = Path(str(source.get("location") or ""))
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def add_dir(parent: QStandardItem, path: Path, depth: int = 0) -> None:
    """Recursively add directories and text files without following symlinks."""
    if depth > MAX_DEPTH:
        return
    try:
        children = sorted(path.iterdir(), key=sort_key)[:MAX_ENTRIES]
    except OSError:
        return
    for child in children:
        if child.is_symlink():
            continue
        label = child.name + ("/" if child.is_dir() else size_suffix(child))
        item = QStandardItem(label)
        item.setEditable(False)
        item.setData(str(child), int(Qt.ItemDataRole.UserRole))
        item.setData(child.is_dir(), int(Qt.ItemDataRole.UserRole) + 1)
        parent.appendRow(item)
        if child.is_dir():
            add_dir(item, child, depth + 1)


def sort_key(path: Path) -> tuple[int, str]:
    """Sort directories first, then files alphabetically."""
    return (0 if path.is_dir() else 1, path.name.lower())


def size_suffix(path: Path) -> str:
    """Return a compact human-readable file size label."""
    try:
        size = float(path.stat().st_size)
    except OSError:
        return ""
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024 or unit == "Go":
            return f" ({int(size)} {unit})" if unit == "o" else f" ({size:.0f} {unit})"
        size /= 1024
    return ""


def readable_preview(path: Path) -> str:
    """Pretty-print JSON and return readable text for supported sub-files."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return "Aperçu indisponible pour ce type de fichier."
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Impossible de lire le fichier: {exc}"
    if path.suffix.lower() == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except ValueError:
            pass
    if len(text) > PREVIEW_LIMIT:
        text = text[:PREVIEW_LIMIT] + "\n\n[... aperçu tronqué ...]"
    return text
