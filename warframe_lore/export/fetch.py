"""Réseau : index LZMA + actifs hachés (avec cache local incrémental)."""

from __future__ import annotations

import logging
import urllib.error
import urllib.parse

from .assets import is_valid_asset_payload, sanitize_asset_filename
from .const import CONTENT_BASE, ORIGIN_BASE
from .lzma import decompress_lzma

log = logging.getLogger(__name__)


def fetch_index(client, lang: str) -> list[str]:
    """Télécharge et décompresse ``index_<lang>.txt.lzma``.

    Retourne la liste des noms hachés d'actifs (ex: ``ExportRecipes_en.json
    !00_<hash>``).  Ne lève pas d'exception sur flux partiel.
    """
    url = f"{ORIGIN_BASE}/index_{lang}.txt.lzma"
    log.info("Index %s : %s", lang, url)
    raw = client._http_get(url)
    text = decompress_lzma(raw)
    assets: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Nom d'actif attendu : ``Export<Cat>_<lang>.json!00_<hash>``.
        # Une ligne sans digest (ex: flux LZMA tronqué en plein nom) ne
        # désigne aucun contenu exploitable -> ignorée.
        name, marker, digest = line.partition("!00_")
        if not marker or not digest or not name:
            log.warning("Ligne d'index invalide ignorée : '%s'.", line)
            continue
        assets.append(line)
    log.info("Index %s : %d manifests découverts.", lang, len(assets))
    return assets


def asset_url(client, asset: str) -> str:
    return f"{CONTENT_BASE}/{urllib.parse.quote(asset, safe='!_.-+')}"


def fetch_asset(client, lang: str, asset: str, force: bool = False) -> bytes | None:
    """Récupère l'actif JSON haché, avec cache local par nom haché.

    L'actif déjà présent dans le cache est réutilisé (hash content-addressed
    : un contenu identique porte un nom identique).  Retourne ``None`` si
    le téléchargement échoue (404/403) et que rien n'est en cache.
    """
    filename = sanitize_asset_filename(asset)
    cache_path = client.cache_dir / lang / filename
    category = asset.split("_", 1)[0]
    if cache_path.exists() and not force:
        cached = cache_path.read_bytes()
        if is_valid_asset_payload(cached, category):
            log.debug("Cache %s : %s réutilisé.", lang, asset)
            return cached
        log.warning("Cache corrompu pour %s/%s : re-téléchargement.",
                    lang, asset)
    url = asset_url(client, asset)
    try:
        payload = client._http_get(url)
    except urllib.error.HTTPError as error:
        log.warning("Actif indisponible %s (%s) : %s", asset, url,
                    error.code)
        return None
    except urllib.error.URLError as error:
        log.warning("Actif injoignable %s (%s) : %s", asset, url,
                    error.reason)
        return None
    # On ne met JAMAIS en cache un payload invalide (il serait réutilisé
    # à l'infini par hash-addressing en masquant la corruption).
    if not is_valid_asset_payload(payload, category):
        log.warning("Payload invalide pour %s (%s) : non mis en cache.",
                    asset, url)
        return payload
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Écriture atomique : un crash en plein write ne laisse pas un cache
    # tronqué qui passerait la validation au prochain run.
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(cache_path)
    return payload