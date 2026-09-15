"""Media index construction: manifest + public names (with caching)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .const import MANIFEST_FAMILIES, MANIFEST_MIRROR_URL
from .names import normalize_key, sanitize_filename
from .network import download_to

log = logging.getLogger(__name__)


def load_and_cache_manifest(cache_dir: Path, force: bool,
                            timeout: int) -> tuple[dict, dict]:
    """Return ``(uniqueName->textureLocation, filename->textureLocation)``."""
    manifest_path = cache_dir / "ExportManifest.json"
    if not manifest_path.exists() or force:
        log.info("Downloading ExportManifest.json (%s)",
                 MANIFEST_MIRROR_URL)
        download_to(MANIFEST_MIRROR_URL, manifest_path, timeout)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = data.get("Manifest") if isinstance(data, dict) else data
    entries = entries or []
    texture: dict[str, str] = {}
    by_file: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        uid = item.get("uniqueName")
        location = item.get("textureLocation")
        if not uid or not location:
            continue
        texture[uid] = location
        by_file[sanitize_filename(location)] = location
    log.debug("ExportManifest: %d entries.", len(texture))
    return texture, by_file


def load_and_cache_names(cache_dir: Path, force: bool, timeout: int) -> dict:
    """Index ``normalised key -> uniqueName`` for page titles / speakers."""
    names_path = cache_dir / "entity_names.json"
    if names_path.exists() and not force:
        data = json.loads(names_path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    names: dict[str, str] = {}
    try:
        from ..export import PublicExportClient
    except ImportError:  # boutique: at worst, index without names
        log.warning("PublicExportClient unavailable (names ignored).")
        return names
    client = PublicExportClient(cache_dir=cache_dir.parent, langs=("en",))
    client.cache_dir.mkdir(parents=True, exist_ok=True)
    assets = client.fetch_index("en")
    for asset in assets:
        family = asset.split("_", 1)[0]
        if family not in MANIFEST_FAMILIES:
            continue
        payload = client.fetch_asset("en", asset, force=force)
        if payload is None:
            continue
        for uid, name in iter_entities(client, family, payload):
            key = normalize_key(name)
            if key and key not in names:
                names[key] = uid
    cache_dir.mkdir(parents=True, exist_ok=True)
    names_path.write_text(
        json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return names


def iter_entities(client, family: str, payload: bytes) -> list[tuple[str, str]]:
    """``(uniqueName, name)`` for a manifest family.

    Known families go through ``PublicExportClient``'s extractor; others
    (Sentinels, Drones, …) are read directly (format
    ``{"Export<Family>": [{"uniqueName", "name", ...}]}``)."""
    if family in client.categories:
        try:
            return [(entity.entity_id, entity.name)
                    for entity in
                    client.iter_entities_for("en", family, payload)]
        except (KeyError, ValueError):
            pass
    out: list[tuple[str, str]] = []
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return out
    entries = data.get(family) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return out
    for item in entries:
        if isinstance(item, dict):
            uid = item.get("uniqueName")
            name = item.get("name")
            if uid and name:
                out.append((uid, name))
    return out
