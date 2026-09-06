"""Découpage intelligent du contenu nettoyé en chunks (préparation RAG).

Stratégie en deux passes (équivalent natif et robuste de
``langchain-text-splitters``, sans dépendance lourde) :

Passe 1 - structurelle (markdown-aware)
    On découpe le Markdown à chaque titre ``#`` / ``##`` / ``###``.  La
    hiérarchie des titres est capturée sous forme de métadonnées
    (ex: ``{"Header 1": "Lore", "Header 2": "L'Ancienne Guerre"}``) et
    associée au chunk.  Un bloc ``> **Amir:** ...`` (dialogue) est traité
    selon le mode dialogue.

Passe 2 - récursive avec chevauchement
    Pour les sections restées trop denses, on re-découpe avec un séparateur
    récursif qui privilégie ``\\n\\n`` puis ``.`` (jamais de phrase coupée
    en plein milieu), avec un chevauchement contrôlé.

Chaque chunk devient une ligne de ``lore_chunks`` (``chunk_index`` +
``content_markdown`` + ``metadata`` JSONB).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Pointeurs de navigation KIM (wiki) en tête de ligne de dialogue
# (``> **{Continues/Same/Jump ...}``, préfixés ``{If ...}``, ``> **>``,
# ``> >``) et pointeurs embarqués (fermés) : artefacts à purger des chunks.
# ``{Convo. ends.}`` est volontairement conservé (marqueur terminal du sim).
_KIM_POINTER_LINE_CHUNK = re.compile(
    r"(?im)^>\s*\*{0,3}\s*>?\s*(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
_KIM_INLINE_NAV_CHUNK = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
_KIM_POSITION_CHUNK = re.compile(r"\{P\d+\}", re.I)
_KIM_CONDITION_CHUNK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)


def _strip_kim_chunk_meta(markdown: str) -> str:
    """Purge les instructions de continuité/condition KIM du texte à découper."""
    text = _KIM_POINTER_LINE_CHUNK.sub("", markdown or "")
    text = _KIM_INLINE_NAV_CHUNK.sub("", text)
    text = _KIM_CONDITION_CHUNK.sub("", text)
    text = _KIM_POSITION_CHUNK.sub("", text)
    return re.sub(r"[ \t]+(?=\n)", "", text)

# Taille cible (en caractères) par défaut - Pitch Phase 2.5 : 1000-1500.
DEFAULT_CHUNK_MAX_CHARACTERS = 1200
# Chevauchement par défaut - Pitch Phase 2.5 : 150-200.
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 175
# Taille cible pour les dialogues (sessions entières, contexte préservé).
DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS = 2500
DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS = 250

_HEADING_TITLE_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
# Ligne de dialogue KIM : '> **Amir:** texte' (le ':' est DANS le gras :
# '**' + 'Amir:' + '**').  On capture le nom du locuteur.
_BLOCKQUOTE_SPEAKER_PATTERN = re.compile(
    r"^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*")

# Séparateurs pour la passe récursive, par ordre de préférence.
_RECURSIVE_SEPARATORS = [
    "\n\n",   # frontière de paragraphe (priorité max).
    "\n",     # frontière de ligne.
    ". ",     # frontière de phrase.
    "! ",
    "? ",
    " ",      # dernier recours : mot.
]


@dataclass(frozen=True)
class RAGChunk:
    """Un chunk prêt pour l'embedding / le stockage RAG."""

    chunk_index: int
    content_markdown: str
    # Métadonnées JSONB : hiérarchie de titres (Header 1/2/3) + speakers.
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkManager:
    """Découpe un Markdown nettoyé en chunks sémantiques + métadonnées.

    Args:
        chunk_max_characters: taille cible d'un chunk (passe 2).
        chunk_overlap_characters: chevauchement entre chunks consécutifs.
        dialogue_chunk_max_characters: taille cible mode dialogue.
        dialogue_chunk_overlap_characters: chevauchement mode dialogue.
    """

    def __init__(
        self,
        chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        chunk_overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
        dialogue_chunk_max_characters: int = (
            DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS),
        dialogue_chunk_overlap_characters: int = (
            DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS),
    ) -> None:
        self.chunk_max_characters = chunk_max_characters
        self.chunk_overlap_characters = chunk_overlap_characters
        self.dialogue_chunk_max_characters = dialogue_chunk_max_characters
        self.dialogue_chunk_overlap_characters = (
            dialogue_chunk_overlap_characters)

    # ------------------------------------------------------------------ split
    def split(self, markdown_text: str, is_dialogue: bool = False) -> list[RAGChunk]:
        """Découpe un Markdown en chunks ordonnés (0-based chunk_index)."""
        if markdown_text:
            markdown_text = _strip_kim_chunk_meta(markdown_text)
        if not markdown_text or not markdown_text.strip():
            return []

        if is_dialogue:
            return self._split_dialogue(markdown_text)

        # Passe 1 -- blocs structurels avec hiérarchie de titres.
        structural_blocks = self._split_on_heading_blocks(markdown_text)

        chunks: list[RAGChunk] = []
        for block, headers in structural_blocks:
            block_sections = self._recursive_split(
                block, self.chunk_max_characters,
                self.chunk_overlap_characters)
            for section_text in block_sections:
                if not section_text.strip():
                    continue
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown=section_text.strip(),
                    metadata=dict(headers),
                ))
        return chunks

    # ----------------------------------------------------------- passe 1
    def _split_on_heading_blocks(
        self, markdown_text: str,
    ) -> list[tuple[str, dict[str, str]]]:
        """Éclate en blocs délimités par les titres, avec hiérarchie.

        Retourne ``[(texte, {header_level: titre, ...}), ...]``.
        """
        blocks: list[tuple[str, dict[str, str]]] = []
        current_lines: list[str] = []
        current_headers: dict[str, str] = {}

        for line in markdown_text.split("\n"):
            heading_match = _HEADING_TITLE_PATTERN.match(line.strip())
            if heading_match is not None:
                # Termine le bloc courant (s'il a du contenu non-titre).
                if current_lines:
                    blocks.append(("\n".join(current_lines),
                                   dict(current_headers)))
                # Récupère la nouvelle hiérarchie : le titre courant écrase
                # les niveaux supérieurs, les niveaux inférieurs tombent.
                heading_level = len(heading_match.group(1))
                heading_title = heading_match.group(2).strip()
                new_headers = dict(current_headers)
                new_headers[f"Header {heading_level}"] = heading_title
                # Supprime les sous-niveaux qui venaient APRÈS ce titre
                # (ex: un '###' avant un '##' nouveau doit être oublié).
                for level in range(heading_level + 1, 7):
                    new_headers.pop(f"Header {level}", None)
                current_headers = new_headers
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            blocks.append(("\n".join(current_lines), dict(current_headers)))
        return blocks

    # ----------------------------------------------------------- passe 2
    def _recursive_split(
        self, text: str, chunk_max_characters: int,
        chunk_overlap_characters: int,
    ) -> list[str]:
        """Découpe récursivement un texte en se limitant aux séparateurs."""
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) <= chunk_max_characters:
            return [text]
        return _recursive_character_split(
            text, list(_RECURSIVE_SEPARATORS),
            chunk_max_characters, chunk_overlap_characters)

    # ----------------------------------------------------------- dialogue
    def _split_dialogue(self, markdown_text: str) -> list[RAGChunk]:
        """Découpe un log de dialogue (KIM / JDR / quêtes).

        Chunks plus larges pour englober une session entière.  En cas de
        coupure, le chunk suivant conserve via ``metadata["speakers"]`` la
        liste des interlocuteurs présents dans la scène.

        Les lignes hors dialogue (note d'usage, branches, texte libre)
        n'alimentent pas ``speakers`` : seules les lignes ``> **Nom:**``
        identifient un locuteur réel.
        """
        lines = markdown_text.split("\n")
        chunk_lines: list[str] = []
        per_chunk_speakers: list[str] = []
        chunks: list[RAGChunk] = []

        max_characters = self.dialogue_chunk_max_characters
        overlap_characters = self.dialogue_chunk_overlap_characters
        step_size = max(1, max_characters - overlap_characters)

        current_size = 0
        for line in lines:
            if not line.strip():
                continue
            speaker = _line_speaker(line)
            line_size = len(line) + 1  # +1 pour le saut de ligne.
            if current_size + line_size > max_characters and chunk_lines:
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown="\n".join(chunk_lines),
                    metadata=_speakers_metadata(per_chunk_speakers),
                ))
                # Conserve les speakers du chunk précédent par sécurité
                # (le contexte des interlocuteurs ne doit jamais se perdre).
                transition_speakers = list(dict.fromkeys(
                    per_chunk_speakers + ([speaker] if speaker else [])))
                chunk_lines = [line]
                per_chunk_speakers = transition_speakers
                current_size = line_size
                if speaker:
                    per_chunk_speakers.append(speaker)
                continue

            chunk_lines.append(line)
            if speaker:
                per_chunk_speakers.append(speaker)
            current_size += line_size

            # Fallback : une ligne de dialogue devenue trop grande (rare)
            # est coupée en morceaux durs sans détruire la métadonnée.
            if line_size > max_characters:
                for piece_start in range(0, len(line), step_size):
                    piece = line[piece_start:piece_start + max_characters]
                    chunks.append(RAGChunk(
                        chunk_index=len(chunks),
                        content_markdown=piece,
                        metadata=_speakers_metadata(per_chunk_speakers),
                    ))

        if chunk_lines:
            chunks.append(RAGChunk(
                chunk_index=len(chunks),
                content_markdown="\n".join(chunk_lines),
                metadata=_speakers_metadata(per_chunk_speakers),
            ))
        return chunks


# ---------------------------------------------------------------------------
# Helper functions (module-level, réutilisables).
# ---------------------------------------------------------------------------
def _speakers_metadata(speakers: list[str]) -> dict[str, Any]:
    """Construit le dict ``metadata`` d'un chunk de dialogue.

    Renvoie ``{}`` si aucun locuteur réel (préambule / notes hors dialogue) ;
    sinon ``{"speakers": [noms uniques, ordre d'apparition]}``.
    """
    unique_speakers = list(dict.fromkeys(speakers))
    if not unique_speakers:
        return {}
    return {"speakers": unique_speakers}


def _line_speaker(line: str) -> str | None:
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


def _recursive_character_split(
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
        return _hard_split(text, chunk_max_characters, chunk_overlap_characters)

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
            final_chunks.extend(_hard_split(
                chunk, chunk_max_characters, chunk_overlap_characters))

    return _apply_overlap(final_chunks, chunk_max_characters,
                          chunk_overlap_characters)


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


def _hard_split(text: str, chunk_max_characters: int,
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


# ---------------------------------------------------------------------------
# API de compatibilité (utilisée par les tests / l'ancienne interface).
# ---------------------------------------------------------------------------
def chunk_markdown(
    markdown_text: str,
    chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
    chunk_overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS,
) -> list[str]:
    """Découpe un Markdown en blocs (ancienne API, sans métadonnées)."""
    manager = ChunkManager(
        chunk_max_characters=chunk_max_characters,
        chunk_overlap_characters=chunk_overlap_characters,
    )
    return [chunk.content_markdown
            for chunk in manager.split(markdown_text, is_dialogue=False)]