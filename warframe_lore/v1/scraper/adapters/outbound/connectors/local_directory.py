"""Generic recursive connector for local structured-document directories."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, cast

from ....ports.outbound.sources import CollectedPage, ConnectorContext
from ....security.policy import classify_suffix, path_suffix
from ....security.scanner import scan_payload

LOGGER = logging.getLogger("warframe_lore.v1.connectors.local_directory")
ALLOWED_SUFFIXES = frozenset({".json", ".jsonl", ".md", ".markdown", ".txt"})
CONTENT_TYPES = {
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}
LANGUAGE_KEYS = ("language", "lang", "locale")
MAX_FILE_BYTES = 5_000_000


class LocalDirectoryConnector:
    """Discover safe structured files below one local source directory."""

    name = "local_directory"
    kinds = ("local_directory", "document")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        """Handle explicit directory sources and any existing local directory."""
        location = str(source.get("location", "")).strip()
        return str(source.get("kind", "")) == self.name or (
            bool(location) and Path(location).is_dir()
        )

    def collect(
        self, source: dict[str, Any], _ctx: ConnectorContext
    ) -> list[CollectedPage]:
        """Return one page per safe file, keyed by a stable absolute path."""
        root = Path(str(source.get("location", ""))).resolve()
        pages: list[CollectedPage] = []
        for path in sorted(root.rglob("*")):
            page = _to_page(path, root)
            if page is not None:
                pages.append(page)
        return pages


def _to_page(path: Path, root: Path) -> CollectedPage | None:
    """Convert one safe file into a collected page, or log why it is skipped."""
    if path.is_symlink() or not path.is_file():
        return None
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        _skip(path, root, ("blocked_outside_root", "Fichier hors du dossier source."))
        return None
    suffix = path.suffix.lower()
    verdict = classify_suffix(path_suffix(path.name))
    if verdict is not None or suffix not in ALLOWED_SUFFIXES:
        _skip(path, root, verdict)
        return None
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        LOGGER.warning(
            "local_directory unreadable file=%s error=%s", _relative(path, root), exc
        )
        return None
    if len(raw) > MAX_FILE_BYTES:
        _skip(path, root, ("blocked_max_bytes", "Fichier trop volumineux."))
        return None
    content_type = CONTENT_TYPES.get(suffix, "text/plain")
    scan = scan_payload(str(path), content=raw, content_type=content_type)
    if not scan.allowed:
        _skip(path, root, (scan.code, scan.reason))
        return None
    try:
        content, language = _parse(suffix, raw)
    except (json.JSONDecodeError, ValueError) as exc:
        LOGGER.warning(
            "local_directory invalid_json file=%s error=%s", _relative(path, root), exc
        )
        return None
    return CollectedPage(
        title=_relative(path, root),
        url=str(resolved),
        content=content,
        raw=raw,
        content_type=content_type,
        metadata={
            "docType": suffix.lstrip("."),
            "language": language,
            "contentHash": hashlib.sha256(raw).hexdigest(),
        },
    )


def _parse(suffix: str, raw: bytes) -> tuple[str, str]:
    """Return clean human-readable text and the declared language."""
    text = raw.decode("utf-8", errors="replace")
    if suffix not in {".json", ".jsonl"}:
        return text, ""
    payload = json.loads(text) if suffix == ".json" else [
        json.loads(line) for line in text.splitlines() if line.strip()
    ]
    language = _language(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2), language


def _language(payload: Any) -> str:
    """Read an explicit fr/en language marker from structured data."""
    if not isinstance(payload, dict):
        return ""
    values = [payload.get(key) for key in LANGUAGE_KEYS]
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        values.extend(cast(dict[str, Any], metadata).get(key) for key in LANGUAGE_KEYS)
    for value in values:
        if isinstance(value, str) and value.strip().lower()[:2] in {"fr", "en"}:
            return value.strip().lower()[:2]
    return ""


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _skip(path: Path, root: Path, verdict: tuple[str, str] | None) -> None:
    reason = f"{verdict[0]}: {verdict[1]}" if verdict else "unsupported extension"
    LOGGER.info(
        "local_directory skipped file=%s reason=%s", _relative(path, root), reason
    )
