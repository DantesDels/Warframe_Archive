"""Instructions de dialogue KIM (wiki) : pointeurs et marqueurs de navigation.

``{Convo. ends.}`` est volontairement conservé (marqueur terminal consommé
par le flow-chart du serveur) ; les pointeurs de continuation/conditions/
positions disparaissent du Markdown servi et des chunks du modèle RAG.
"""

from __future__ import annotations

import re

# Instruction de navigation KIM en tête de ligne de dialogue (pointeurs wiki) :
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# et les variantes préfixées par une ou plusieurs conditions
# ``> **{If ...} {If ...} {Continues ...}`` ou ``> **> {...`` / ``> > {...``.
# Le mot-clé de navigation vit TOUJOURS dans une accolade ; la fermeture de
# l'accolade n'est pas exigée.  ``{If ...}`` et ``{Convo. ends.}`` ne
# contiennent pas ces mots-clés -> non concernés.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
# Pointeur de navigation embarqué (fermé) dans un message : retiré du texte,
# sauf si le contenu évoque un terminal ``{... ends ...}`` (ex: ``{Convo.
# Ends. Followed by jumpscare image.}``).
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_ARTIFACT_LINE = re.compile(r"^\s*>?\s*\*{1,2}\s*$")


def strip_kim_dialog_instructions(markdown: str) -> str:
    """Retire définitivement les instructions d'enchaînement KIM (``{...}``).

    Purgées : lignes-pointeurs de continuation, conditions de branche
    (``{If ...}``) et marqueurs de position (``{P1}`` …).  Elles ne doivent
    apparaître ni dans l'interface, ni dans les chunks du modèle RAG.
    """
    if not markdown:
        return markdown
    text = _KIM_POINTER_LINE.sub("", markdown)
    text = _KIM_INLINE_NAV.sub("", text)
    text = _KIM_CONDITION_MARK.sub("", text)
    text = _KIM_POSITION_MARK.sub("", text)
    text = _KIM_ARTIFACT_LINE.sub("", text)
    # Résidus de retrait d'un ``{If ...}`` entre ``> **`` et le nom :
    # ``> ** Arthur:**`` -> ``> **Arthur:**`` (ouverture seule, jamais la
    # paire de fermeture ``** texte``).
    text = re.sub(r"(?m)(^\s*[*>\-]+\s*)\*\*[ \t]+(?=\w)", r"\1**", text)
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    return text


__all__ = ["strip_kim_dialog_instructions"]