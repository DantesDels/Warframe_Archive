"""Filesystem adapter for VaultExporterPort (Obsidian vault layout)."""

from __future__ import annotations

import os
from pathlib import Path


class ObsidianVaultExporter:
    """Read and write vault notes under one root directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ValueError(f"path escapes the vault: {relative_path!r}")
        return target

    def read_note(self, relative_path: str) -> str | None:
        path = self._resolve(relative_path)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def write_note(self, relative_path: str, content: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    def list_notes(self) -> list[str]:
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*.md")
        )
