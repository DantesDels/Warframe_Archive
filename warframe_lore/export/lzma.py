"""Décompression LZMA tolérante aux flux tronqués."""

from __future__ import annotations

import lzma
import logging

log = logging.getLogger(__name__)


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