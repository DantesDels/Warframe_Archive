"""Helpers de découpage (passe 2) : récursif, chevauchement, coupe dure.

Ces fonctions sont pures (aucun état) et réutilisées à la fois par le
``ChunkManager`` structurel et le mode dialogue.
"""

from __future__ import annotations

import re
from typing import Any

# Ligne de dialogue KIM : '> **Amir:** texte' (le ':' est DANS le gras :
# '**' + 'Amir:' + '**').  On capture le nom du locuteur.
_BLOCKQUOTE_SPEAKER_PATTERN = re.compile(
    r"^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*")


def speakers_metadata(speakers: list[str]) -> dict[str, Any]:
    """Construit le dict ``metadata`` d'un chunk de dialogue.

    Renvoie ``{}`` si aucun locuteur réel (préambule / notes hors dialogue) ;
    sinon ``{"speakers": [noms uniques, ordre d'apparition]}``.
    """
    unique_speakers = list(dict.fromkeys(speakers))
    if not unique_speakers:
        return {}
    return {"speakers": unique_speakers}


def line_speaker(line: str) -> str | None:
    """Extrait le nom de locuteur d'une ligne de dialogue ``> **Name:**``.

    Filtre strict : un vrai locuteur KIM est un nom propre court sans
    ponctuation spéciale ni balise de navigation (``(Jump ...``, ``[Jump``,
    ``> ...``).  Les options de dialogue et annotations des pages KIM ne
    sont pas des locuteurs.
    """
    match = _BLOCKQUOTE_SPEAKER_PATTERN.match(line.strip())
    if match is None:
        return None
    candidate = match.group("speaker").strip()
    # Exclut les balises/navigation/branches : crochets, parenthèses,
    # chevrons, accolades, astérisques ou soulignés.
    if not candidate or any(marker in candidate for marker in
                            ("*", "_", "]", "}", "(", "[", ">")):
        return None
    # Un vrai nom de personnage commence par une lettre majuscule, est
    # court (<= 24 chars) et ne contient pas de ponctuation de phrase.
    if not (candidate[0].isalpha() and candidate[0].isupper()):
        return None
    if len(candidate) > 24:
        return None
    if any(character in candidate for character in (".", ",", "?", "!")):
        return None
    return candidate


def recursive_character_split(
    text: str,
    separators: list[str],
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Splitter récursif (équivalent ``RecursiveCharacterTextSplitter``).

    1. On découpe au premier séparateur non présent puis on *fusionne* les
       morceaux consécutifs jusqu'à approcher ``chunk_max_characters`` ;
    2. Tout morceau resté trop grand est re-travaillé avec le séparateur
       suivant (récursif) ;
    3. On applique ensuite un chevauchement : chaque chunk porte la queue
       du chunk précédent pour préserver le contexte.
    """
    if not separators:
        return hard_split(text, chunk_max_characters, chunk_overlap_characters)

    separator = separators[0]
    remaining_separators = separators[1:]

    pieces = text.split(separator)
    if len(pieces) == 1:
        # Le séparateur courant n'est pas dans le texte : séparateur suivant.
        return _recursive_character_split(
            text, remaining_separators,
            chunk_max_characters, chunk_overlap_characters)

    # Fusion des morceaux en chunks proches de la taille cible.
    merged_chunks = _merge_pieces(
        pieces, separator, chunk_max_characters, chunk_overlap_characters)

    final_chunks: list[str] = []
    for chunk in merged_chunks:
        if len(chunk) <= chunk_max_characters:
            final_chunks.append(chunk)
        elif remaining_separators:
            final_chunks.extend(_recursive_character_split(
                chunk, remaining_separators,
                chunk_max_characters, chunk_overlap_characters))
        else:
            # Plus de séparateurs disponibles : coupe dure avec recouvrement.
            final_chunks.extend(hard_split(
                chunk, chunk_max_characters, chunk_overlap_characters))

    return _apply_overlap(final_chunks, chunk_max_characters,
                          chunk_overlap_characters)


def _recursive_character_split(
    text: str,
    separators: list[str],
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Point d'entrée interne de la récursion (délègue à la fonction publique)."""
    return recursive_character_split(
        text, separators, chunk_max_characters, chunk_overlap_characters)


def _merge_pieces(
    pieces: list[str],
    separator: str,
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Assemble des morceaux consécutifs en chunks proches de la cible.

    Le séparateur est recollé après chaque morceau (sauf le dernier) pour
    ne perdre aucune information.
    """
    merged_chunks: list[str] = []
    current_piece = ""

    for index, piece in enumerate(pieces):
        separator_after = separator if index < len(pieces) - 1 else ""
        piece_with_separator = piece + separator_after
        candidate_length = len(current_piece) + len(piece_with_separator)

        if current_piece and candidate_length > chunk_max_characters:
            if current_piece.strip():
                merged_chunks.append(current_piece)
            current_piece = piece_with_separator
        else:
            current_piece += piece_with_separator

    if current_piece.strip():
        merged_chunks.append(current_piece)
    return merged_chunks


def _apply_overlap(
    chunks: list[str],
    chunk_max_characters: int,
    chunk_overlap_characters: int,
) -> list[str]:
    """Préfixe chaque chunk (sauf le premier) par la queue du précédent.

    Garantit la continuité du contexte entre chunks consécutifs, sans
    dupliquer si le chevauchement est déjà présent, et sans jamais
    dépasser ``chunk_max_characters`` (le contexte ajouté est borné).
    """
    if len(chunks) <= 1 or chunk_overlap_characters <= 0:
        return chunks

    result: list[str] = []
    for index, chunk in enumerate(chunks):
        if index == 0:
            result.append(chunk)
            continue
        previous_tail = chunks[index - 1][-chunk_overlap_characters:]
        if chunk.startswith(previous_tail):
            result.append(chunk)
            continue
        # Borde la queue préfixée pour rester ≤ chunk_max_characters.
        room_for_overlap = max(0, chunk_max_characters - len(chunk))
        bounded_tail = previous_tail[-room_for_overlap:] if room_for_overlap else ""
        result.append(bounded_tail + chunk)
    return result


def hard_split(text: str, chunk_max_characters: int,
               chunk_overlap_characters: int) -> list[str]:
    """Découpe un texte très long en morceaux de taille fixe + recouvrement."""
    step_size = chunk_max_characters - chunk_overlap_characters
    if step_size <= 0:
        step_size = chunk_max_characters
    pieces: list[str] = []
    start_index = 0
    while start_index < len(text):
        end_index = start_index + chunk_max_characters
        pieces.append(text[start_index:end_index])
        start_index += step_size
    return pieces