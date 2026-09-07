"""Normalisation des noms de fichiers et clés de correspondance."""

from __future__ import annotations

import re
import unicodedata


def sanitize_filename(texture_location: str) -> str:
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


def normalize_key(value: str) -> str:
    """Clé de correspondance insensible à la casse / aux accents."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text