"""Warframe Public Export — ingestion des entités localisées du jeu.

Pipeline officiel (cf. wiki.warframe.com/w/Public_Export) :
  1. ``https://origin.warframe.com/PublicExport/index_<lang>.txt.lzma``  -> un
     flux LZMA **brut** contenant les noms hachés des manifests (1 par ligne,
     format ``Export<Category>_<lang>.json!00_<hash>``).
  2. Pour chaque nom haché, l'actif est servi par le serveur de contenu :
     ``http://content.warframe.com/PublicExport/Manifest/<nom_haché>``.
     L'actif est un JSON du type ``{"Export<Category>": [ {uniqueName, name,
     description, ...}, ... ]}``.

Le cache est **incrémental et sûr** : le hash ``!00_<hash>`` (content-addressed)
change uniquement quand le contenu change — un actif déjà téléchargé peut être
conservé indéfiniment et on re-synchronise en comparant les hashs de l'index.

Notes d'implémentation :
  * L'index est un flux LZMA en conteneur ``FORMAT_ALONE`` (``5d`` + taille de
    dictionnaire de 4 octets) ; le serveur peut fournir un flux tronqué, on
    tolère donc une décompression partielle (on garde ce qui décode, on logue).
  * On ne télécharge que les catégories d'entités utiles (définies dans
    ``EXPORT_CATEGORIES``) et uniquement les langues demandées (défaut ``en``
    + ``fr``).
"""

from __future__ import annotations

import json
import logging
import lzma
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

ORIGIN_BASE = "https://origin.warframe.com/PublicExport"
CONTENT_BASE = "http://content.warframe.com/PublicExport/Manifest"

DEFAULT_LANGS = ("en", "fr")

# Catégories d'entités retenues pour ``game_entities_i18n``.  Chaque clé est le
# préfixe du manifest ; la valeur est le libellé ``entity_type`` stocké en base.
EXPORT_CATEGORIES: dict[str, str] = {
    "ExportCustoms": "Customs",
    "ExportGear": "Gear",
    "ExportKeys": "Keys",
    "ExportRecipes": "Recipes",
    "ExportRegions": "Regions",
    "ExportRelicArcane": "RelicArcane",
    "ExportResources": "Resources",
    "ExportUpgrades": "Upgrades",
    "ExportWarframes": "Warframes",
    "ExportWeapons": "Weapons",
}


def _sanitize_asset_filename(asset: str) -> str:
    """Nom de fichier sûr pour le cache local (``!00_`` etc. ne sont pas
    valides sur tous les systèmes de fichiers)."""
    return asset.replace("!", "_").replace("/", "_").replace("\\", "_")


def decompress_lzma(data: bytes) -> str:
    """Décompresse un flux LZMA ``FORMAT_ALONE``, en tolérant un flux tronqué.

    Le serveur officiel sert parfois un index raccourci (end-of-stream LZMA
    absent).  On retourne alors le début déjà décodé (les noms hachés valides)
    et on logue un avertissement.
    """
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    out = bytearray()
    position = 0
    while position < len(data) and not decompressor.eof:
        try:
            # Petites tranches : si le flux est tronqué en milieu de paquet,
            # on conserve le maximum de données valides déjà décodées.
            out.extend(decompressor.decompress(
                data[position:position + 64], max_length=1 << 20))
        except lzma.LZMAError:
            log.warning("Index LZMA partiel : fin avant la fin du flux "
                        "(décodé %d octets sur %d).", len(out), len(data))
            break
        position += 64
    return out.decode("utf-8", errors="replace")


def _is_valid_asset_payload(payload: bytes, category: str) -> bool:
    """Vrai si ``payload`` est un actif JSON exploitable.

    Miroir de ce que ``iter_entities_for`` accepte : soit un objet dont la
    clé ``category`` mène à une liste, soit une liste à la racine.  Une
    réponse tronquée, vide ou d'une structure inattendue est considérée
    invalide (à ne pas mettre en cache).
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("JSON illisible (%s)", error)
        return False
    entries = data.get(category) if isinstance(data, dict) else data
    return isinstance(entries, list)


def _as_text(value, *, default: str | None = None) -> str | None:
    """Normalise un champ localisé (``str``, ``list[str]``, ``dict``, ``None``).

    Certains exports (Exemples : mods de combos) portent ``description`` sous
    forme de liste de fragments — on la joint en une chaîne lisible.
    """
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    if isinstance(value, list):
        parts = [_as_text(part) for part in value]
        joined = " ".join(part for part in parts if part)
        return joined or default
    if isinstance(value, dict):
        # ``{"name": ...}`` localisé : on reprend le premier champ texte.
        for key in ("name", "value", "0"):
            if key in value:
                return _as_text(value[key], default=default)
        return default
    return str(value)


class PublicExportClient:
    """Client du Warframe Public Export avec cache local incrémental."""

    def __init__(
        self,
        cache_dir="cache/public_export",
        langs: tuple[str, ...] = DEFAULT_LANGS,
        categories: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.langs = tuple(langs)
        self.categories = dict(categories or EXPORT_CATEGORIES)
        self.timeout = timeout

    # ------------------------------------------------------------- réseau
    def _http_get(self, url: str) -> bytes:
        """GET binaire avec User-Agent navigateur + timeouts raisonnables."""
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def fetch_index(self, lang: str) -> list[str]:
        """Télécharge et décompresse ``index_<lang>.txt.lzma``.

        Retourne la liste des noms hachés d'actifs (ex: ``ExportRecipes_en.json
        !00_<hash>``).  Ne lève pas d'exception sur flux partiel.
        """
        url = f"{ORIGIN_BASE}/index_{lang}.txt.lzma"
        log.info("Index %s : %s", lang, url)
        raw = self._http_get(url)
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

    def asset_url(self, asset: str) -> str:
        return f"{CONTENT_BASE}/{urllib.parse.quote(asset, safe='!_.-+')}"

    def fetch_asset(self, lang: str, asset: str, force: bool = False) -> bytes | None:
        """Récupère l'actif JSON haché, avec cache local par nom haché.

        L'actif déjà présent dans le cache est réutilisé (hash content-addressed
        : un contenu identique porte un nom identique).  Retourne ``None`` si
        le téléchargement échoue (404/403) et que rien n'est en cache.
        """
        filename = _sanitize_asset_filename(asset)
        cache_path = self.cache_dir / lang / filename
        category = asset.split("_", 1)[0]
        if cache_path.exists() and not force:
            cached = cache_path.read_bytes()
            if _is_valid_asset_payload(cached, category):
                log.debug("Cache %s : %s réutilisé.", lang, asset)
                return cached
            log.warning("Cache corrompu pour %s/%s : re-téléchargement.",
                        lang, asset)
        url = self.asset_url(asset)
        try:
            payload = self._http_get(url)
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
        if not _is_valid_asset_payload(payload, category):
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

    # -------------------------------------------------------- extraction
    def iter_entities_for(
        self,
        lang: str,
        category: str,
        payload: bytes,
    ) -> list[tuple[str, str, str, str | None]]:
        """Extrait ``(entity_id, entity_type, lang, name, description)``.

        Le fichier JSON est ``{"Export<Category>": [ ... ]}`` ; chaque entrée
        porte ``uniqueName``, ``name`` (localisé) et ``description`` (localisé).
        Les entrées sans ``uniqueName`` sont ignorées.
        """
        entity_type = self.categories[category]
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            log.warning("JSON illisible pour %s/%s : %s", category, lang, error)
            return []
        entries = data.get(category) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            log.warning("Structure inattendue pour %s/%s (type %s).",
                        category, lang, type(entries).__name__)
            return []
        entities = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            entity_id = item.get("uniqueName")
            if not entity_id:
                continue
            entities.append((
                str(entity_id),
                entity_type,
                lang,
                _as_text(item.get("name"), default="") or "",
                _as_text(item.get("description")),
            ))
        return entities

    async def sync(
        self,
        manager,
        langs: tuple[str, ...] | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        """Synchronise les entités localisées en base.

        Étapes : index par langue -> filtrage des catégories retenues ->
        téléchargement (cache) -> extraction -> upsert into
        ``game_entities_i18n``.

        Returns:
            ``{"entities": N, "assets": M, "skipped": K}`` — N lignes écrites,
            M actifs téléchargés/relus, K actifs manquants (404).
        """
        from warframe_lore.db.manager import SQLDatabaseManager

        if not isinstance(manager, SQLDatabaseManager):
            raise TypeError("manager doit être un SQLDatabaseManager connecté.")

        langs = tuple(langs) if langs else self.langs
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        total_entities = 0
        assets_used = 0
        skipped = 0
        for lang in langs:
            assets = self.fetch_index(lang)
            for asset in assets:
                category = asset.split("_", 1)[0]
                if category not in self.categories:
                    continue
                payload = self.fetch_asset(lang, asset, force=force)
                if payload is None:
                    skipped += 1
                    continue
                assets_used += 1
                entities = self.iter_entities_for(lang, category, payload)
                if entities:
                    written = await manager.upsert_game_entities(entities)
                    total_entities += written
                    log.info("[%s] %s : %d entités.", lang, category, written)
        log.info("Synchronisation Public Export terminée : %d entités, "
                 "%d actifs, %d en échec.", total_entities, assets_used, skipped)
        return {"entities": total_entities, "assets": assets_used,
                "skipped": skipped}