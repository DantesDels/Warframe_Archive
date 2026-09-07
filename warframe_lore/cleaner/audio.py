"""Retrait des noms de fichiers audio (.ogg/.mp3/.wav) du Wiki.

Noms laissés par les lecteurs audio dans les transcriptions de quêtes :
    * jeton unique        -> ``LeekterSlippery.ogg``, ``DCodexA00010Silvana_en.ogg``
    * code créé en deux    -> ``DWraithQM1CrpArrive0060RJCephalon en.ogg``
      morceaux (loc. en)     ``DThroneRoom0050Erra en.mp3`` ``BbPainAmbulas00020 en.ogg``
Noter : ``[a-z0-9_]`` avec re.IGNORECASE accepte aussi les majuscules.
"""

from __future__ import annotations

import re

_AUDIO_LOCALE_TOKEN = re.compile(
    r"\b[a-z0-9_]+[ \t]{1,3}en\.(?:ogg|mp3)\b", re.IGNORECASE)
_AUDIO_FILE_TOKEN = re.compile(r"\b[\w-]+\.(?:ogg|mp3|wav)\b", re.IGNORECASE)


def strip_audio_filenames(markdown: str) -> str:
    """Retire les métadonnées audio du Wiki (noms de fichiers .ogg/.mp3/.wav).

    Passe 1 : le code créé suivi de la locale est supprimé en un seul coup
    (``DThroneRoom0050Erra en.mp3``), sinon la locale ``en.ogg`` orpheline
    resterait collée au texte.
    Passe 2 : tout jeton autonome ``Word.ogg/.mp3/.wav`` restant.
    Passe 3 : les lignes devenues vides ou réduites à un seul locuteur
    (ex: ``> **Angel's song:**`` après suppression du fichier) sont retirées,
    d'où qu'elles viennent.
    """
    if not markdown:
        return markdown
    text = _AUDIO_LOCALE_TOKEN.sub("", markdown)
    text = _AUDIO_FILE_TOKEN.sub("", text)
    lines_out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        body = stripped[1:].strip() if stripped.startswith(">") else stripped
        # Locuteur résiduel seul sur sa ligne : ``> **Angel's song:**``
        body = re.sub(r"^\*\*[^*]*\*\*\s*:?\s*$", "", body)
        # Libellé résiduel seul : ``Angel's song:``
        body = re.sub(
            r"^[A-Za-z][\w'’]*(?:[ -][A-Za-z][\w'’]*)*\s*:\s*$", "", body)
        # Cruft Markdown (``*`` ``_`` ``>`` ``:`` ``"`` ``-`` …) sans texte.
        body = re.sub(r"[>*_:.\"'’\-\u2013\u2014]", "", body).strip()
        if body:
            lines_out.append(line)
    return "\n".join(lines_out)


__all__ = ["strip_audio_filenames"]