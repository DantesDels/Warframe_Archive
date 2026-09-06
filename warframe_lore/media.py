"""Warframe Public Export — index média + images à la demande.

Pipeline officiel (cf. https://wiki.warframe.com/w/Public_Export) :
  * ``ExportManifest.json`` associe chaque ``uniqueName`` à une
    ``textureLocation`` (URI content-addressed, ex: ``/Lotus/Interface/Icons/
    StoreIcons/Weapons/.../Lato.png!00_<hash>``).
  * L'image se télécharge à : ``https://content.warframe.com/PublicExport/``
    + ``textureLocation``.
  * Depuis 2026, ``ExportManifest.json`` n'est plus listé dans
    ``index_<lang>.txt.lzma`` ; on le récupère depuis le miroir maintenu
    automatiquement (calamity-inc/warframe-public-export), qui reflète la
    publication officielle.

Noms publics : les manifests de catégories (``ExportWarframes_en.json``,
``ExportWeapons_en.json``, …) portent ``name`` (localisé) + ``uniqueName`` ;
on les utilise pour mapper un titre de page wiki / un locuteur KIM vers une
image.

Mise en cache : le manifest et les noms sont persistés dans
``cache/public_export/media/`` ; les PNG téléchargés à la demande sont stockés
dans ``<output_dir>/media/`` (consultables hors-ligne ensuite).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

CONTENT_IMAGE_BASE = "https://content.warframe.com/PublicExport"
MANIFEST_MIRROR_URL = (
    "https://raw.githubusercontent.com/calamity-inc/warframe-public-export/"
    "senpai/ExportManifest.json"
)

# Familles de manifests dont on extrait les noms publics (``name`` -> uid).
MANIFEST_FAMILIES = (
    "ExportCustoms", "ExportDrones", "ExportFlavour", "ExportFusionBundles",
    "ExportGear", "ExportKeys", "ExportRecipes", "ExportRegions",
    "ExportRelicArcane", "ExportResources", "ExportSentinels",
    "ExportSortieRewards", "ExportUpgrades", "ExportWarframes",
    "ExportWeapons",
)


def _sanitize_filename(texture_location: str) -> str:
    """Nom de fichier local stable pour une ``textureLocation``.

    Ex: ``/Lotus/Interface/Icons/StoreIcons/Weapons/.../Lato.png!00_<hash>``
    -> ``Lato.png__00_<hash>.png`` (unique via le hash content-addressed).
    """
    base = texture_location.rsplit("/", 1)[-1]
    name, _, hash_part = base.partition("!00_")
    if hash_part:
        stem = name + "__00_" + hash_part
    else:
        stem = name
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", stem)


def _normalize_key(value: str) -> str:
    """Clé de correspondance insensible à la casse / aux accents."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


class MediaIndex:
    """Index média (uniqueName->texture, titre->image) + cache PNG local.

    Construction paresseuse et thread-safe : le premier accès réseau
    (manifest 4,7 Mo + manifests de catégories) est tolérant à l'échec —
    sans réseau l'interface continue (simplement sans images).
    """

    def __init__(self, output_dir: Path, cache_dir="cache/public_export/media",
                 timeout: int = 60) -> None:
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.media_dir = self.output_dir / "media"
        self._lock = threading.RLock()
        self._ready = False
        self._attempted = False
        # uniqueName -> textureLocation ; filename -> textureLocation
        self._texture: dict[str, str] = {}
        self._by_file: dict[str, str] = {}
        # clé normalisée (titre / locuteur) -> uniqueName
        self._names: dict[str, str] = {}

    # ------------------------------------------------------------- réseau
    def _http_get(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _download_to(self, url: str, target: Path) -> Path:
        payload = self._http_get(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return target

    # -------------------------------------------------------- construction
    def ensure(self, force: bool = False) -> bool:
        """Charge (ou télécharge) l'index média. Idempotent, thread-safe."""
        with self._lock:
            if self._ready and not force:
                return True
            if self._attempted and not force:
                return self._ready
            self._attempted = True
            try:
                self._ensure_manifest(force=force)
                self._ensure_names(force=force)
                self._ready = True
                log.info("Index média prêt : %d textures, %d noms.",
                         len(self.texture_map()), len(self._names))
            except Exception as exc:  # noqa: BLE001 (mode best-effort)
                log.warning("Index média indisponible : %s", exc)
                self._ready = False
            return self._ready

    def _ensure_manifest(self, force: bool) -> None:
        manifest_path = self.cache_dir / "ExportManifest.json"
        if not manifest_path.exists() or force:
            log.info("Téléchargement d'ExportManifest.json (%s)",
                     MANIFEST_MIRROR_URL)
            self._download_to(MANIFEST_MIRROR_URL, manifest_path)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = data.get("Manifest") if isinstance(data, dict) else data
        entries = entries or []
        self._texture = {}
        self._by_file = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            uid = item.get("uniqueName")
            location = item.get("textureLocation")
            if not uid or not location:
                continue
            self._texture[uid] = location
            self._by_file[_sanitize_filename(location)] = location
        log.debug("ExportManifest : %d entrées.", len(self._texture))

    def _ensure_names(self, force: bool) -> None:
        names_path = self.cache_dir / "entity_names.json"
        if names_path.exists() and not force:
            data = json.loads(names_path.read_text(encoding="utf-8"))
            self._names = {str(k): str(v) for k, v in data.items()}
            return
        self._names = {}
        try:
            from .export import PublicExportClient
        except ImportError:  # boutique : au pire, index sans noms
            log.warning("PublicExportClient indisponible (noms ignorés).")
            return
        client = PublicExportClient(cache_dir=self.cache_dir.parent, langs=("en",))
        client.cache_dir.mkdir(parents=True, exist_ok=True)
        assets = client.fetch_index("en")
        for asset in assets:
            family = asset.split("_", 1)[0]
            if family not in MANIFEST_FAMILIES:
                continue
            payload = client.fetch_asset("en", asset, force=force)
            if payload is None:
                continue
            for uid, name in self._iter_entities(client, family, payload):
                key = _normalize_key(name)
                if key and key not in self._names:
                    self._names[key] = uid
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        names_path.write_text(
            json.dumps(self._names, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _iter_entities(client, family: str, payload: bytes) -> list[tuple[str, str]]:
        """``(uniqueName, name)`` pour une famille de manifest.

        Les familles connues de ``PublicExportClient`` passent par son
        extracteur ; les autres (Sentinels, Drones, …) sont lues directement
        (format ``{"Export<Family>": [{"uniqueName", "name", ...}]}``)."""
        if family in client.categories:
            try:
                return [(uid, name)
                        for uid, _, _, name, _ in
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

    # ------------------------------------------------------------ requêtes
    def available(self) -> bool:
        return self._ready

    def texture_map(self) -> dict[str, str]:
        return dict(self._texture)

    def filename_for_unique(self, unique_name: str) -> str | None:
        location = self._texture.get(unique_name)
        if not location:
            return None
        return _sanitize_filename(location)

    def filename_for_title(self, title: str) -> str | None:
        uid = self._names.get(_normalize_key(title))
        return self.filename_for_unique(uid) if uid else None

    def lookup(self, key: str) -> str | None:
        """Titre de page ou nom de locuteur -> nom de fichier image."""
        return self.filename_for_title(key)

    # ------------------------------------------------------- image serveur
    def fetch_image(self, filename: str) -> bytes | None:
        """PNG mis en cache dans ``<output_dir>/media`` (téléchargement à la
        première demande). Retourne ``None`` si introuvable."""
        texture_location = self._by_file.get(filename)
        if not texture_location:
            return None
        local = self.media_dir / filename
        if local.is_file():
            return local.read_bytes()
        url = CONTENT_IMAGE_BASE + texture_location
        try:
            self._download_to(url, local)
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            log.warning("Image indisponible %s (%s) : %s",
                        filename, url, getattr(error, "code", error.reason))
            return None
        return local.read_bytes()

    def media_payload(
        self,
        page_titles_by_bucket: dict[str, list[str]],
        speakers: list[str],
    ) -> dict:
        """Charge utile JSON pour ``/api/media``.

        Ne contient que les images pertinentes pour l'archive (titres de
        pages + locuteurs KIM + représentants de bucket) — léger pour l'UI.
        """
        titles: dict[str, str] = {}
        buckets: dict[str, str] = {}
        for bucket_id, page_titles in page_titles_by_bucket.items():
            for title in page_titles:
                filename = self.lookup(title)
                if filename:
                    titles[title] = filename
                    if bucket_id not in buckets:
                        buckets[bucket_id] = filename
        speaker_images: dict[str, str] = {}
        for speaker in speakers:
            filename = self.lookup(speaker)
            if filename:
                speaker_images[speaker] = filename
        return {
            "available": self._ready,
            "count": len(self._texture),
            "titles": titles,
            "speakers": speaker_images,
            "buckets": buckets,
        }