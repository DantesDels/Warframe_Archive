"""Networking: LZMA index + hashed assets (with incremental local cache)."""

from __future__ import annotations

import logging
import urllib.error
import urllib.parse

from .assets import is_valid_asset_payload, sanitize_asset_filename
from .const import CONTENT_BASE, ORIGIN_BASE
from .lzma import decompress_lzma

log = logging.getLogger(__name__)


def fetch_index(client, lang: str) -> list[str]:
    """Downloads and decompresses ``index_<lang>.txt.lzma``.

    Returns the list of hashed asset names (e.g. ``ExportRecipes_en.json
    !00_<hash>``).  Does not raise on a partial stream.
    """
    url = f"{ORIGIN_BASE}/index_{lang}.txt.lzma"
    log.info("Index %s: %s", lang, url)
    raw = client._http_get(url)
    text = decompress_lzma(raw)
    assets: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Expected asset name: ``Export<Cat>_<lang>.json!00_<hash>``.
        # A line without a digest (e.g. LZMA stream truncated mid-name)
        # refers to no usable content -> skipped.
        name, marker, digest = line.partition("!00_")
        if not marker or not digest or not name:
            log.warning("Invalid index line ignored: '%s'.", line)
            continue
        assets.append(line)
    log.info("Index %s: %d manifests found.", lang, len(assets))
    return assets


def asset_url(client, asset: str) -> str:
    return f"{CONTENT_BASE}/{urllib.parse.quote(asset, safe='!_.-+')}"


def fetch_asset(client, lang: str, asset: str, force: bool = False) -> bytes | None:
    """Fetches the hashed JSON asset, with local cache by hashed name.

    An asset already present in the cache is reused (content-addressed
    hash: identical content has an identical name).  Returns ``None`` if
    the download fails (404/403) and nothing is cached.
    """
    filename = sanitize_asset_filename(asset)
    cache_path = client.cache_dir / lang / filename
    category = asset.split("_", 1)[0]
    if cache_path.exists() and not force:
        cached = cache_path.read_bytes()
        if is_valid_asset_payload(cached, category):
            log.debug("Cache %s: %s reused.", lang, asset)
            return cached
        log.warning("Corrupted cache for %s/%s: re-downloading.",
                    lang, asset)
    url = asset_url(client, asset)
    try:
        payload = client._http_get(url)
    except urllib.error.HTTPError as error:
        log.warning("Asset unavailable %s (%s): %s", asset, url,
                    error.code)
        return None
    except urllib.error.URLError as error:
        log.warning("Asset unreachable %s (%s): %s", asset, url,
                    error.reason)
        return None
    # We NEVER cache an invalid payload (it would be reused indefinitely
    # by hash-addressing while masking corruption).
    if not is_valid_asset_payload(payload, category):
        log.warning("Invalid payload for %s (%s): not cached.",
                    asset, url)
        return payload
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: a crash mid-write leaves no truncated cache that would
    # pass validation on the next run.
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(cache_path)
    return payload
