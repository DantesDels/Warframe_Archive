"""Miroir de la datamine KIM — téléchargement du dépôt GitHub en cache."""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from warframe_lore.kim_dm.constants import (
    DIALOGUE_FILES,
    DICTS_DIRNAME,
    DATA_DIRNAME,
    RAW_BASE,
    _USER_AGENT,
)


def _download(url: str, target: Path, *, timeout: float = 60.0) -> None:
    """Télécharge ``url`` vers ``target`` (UA + retries simples)."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise OSError(f"HTTP {response.status}")
                target.write_bytes(response.read())
            return
        except Exception as exc:  # noqa: BLE001  (repli après retries)
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise OSError(f"Échec du téléchargement de {url}: {last_error}")


def mirror_kim_dm(output_dir: Path, *, langs: tuple[str, ...] = ("en",),
                  force: bool = False) -> tuple[list[str], list[str]]:
    """Télécharge le miroir KIM (graphes + dictionnaires) dans ``out/kim_dm``.

    Retourne ``(téléchargés, échecs)`` — jamais d'exception pour un fichier
    isolé : les fichiers introuvables n'interrompent pas le reste du miroir.
    """
    root = Path(output_dir) / "kim_dm"
    downloaded: list[str] = []
    failed: list[str] = []
    for subdir in (DATA_DIRNAME, DICTS_DIRNAME):
        (root / subdir).mkdir(parents=True, exist_ok=True)

    def _mirror_file(rel: str) -> None:
        target = root / rel
        if not force and target.is_file():
            return
        try:
            _download(RAW_BASE + rel, target)
            downloaded.append(rel)
        except OSError as exc:
            failed.append(f"{rel} ({exc})")

    for lang in langs:
        _mirror_file(f"{DICTS_DIRNAME}/{lang}.json")
    for filename in DIALOGUE_FILES:
        _mirror_file(f"{DATA_DIRNAME}/{filename}")
    return downloaded, failed