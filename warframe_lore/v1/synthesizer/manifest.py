"""Synthesizer manifest: content hashes and human-lock protection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .frontmatter import parse_frontmatter
from .ports import VaultExporterPort

MANIFEST_PATH = ".synthesizer/manifest.json"


def content_hash(payload: dict[str, Any]) -> str:
    """Stable SHA-256 of a note input payload (incrementality key)."""
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_manifest(exporter: VaultExporterPort) -> dict[str, str]:
    raw = exporter.read_note(MANIFEST_PATH)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def save_manifest(exporter: VaultExporterPort, manifest: dict[str, str]) -> None:
    exporter.write_note(
        MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def is_locked(note_content: str) -> bool:
    """True when the existing note frontmatter carries locked: true."""
    fields, _ = parse_frontmatter(note_content)
    return fields.get("locked") is True
