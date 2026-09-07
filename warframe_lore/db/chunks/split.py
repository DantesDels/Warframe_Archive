"""``ChunkManager`` : découpage structurel (passe 1) + dialogue.

Passe 1 - structurelle (markdown-aware) : on découpe le Markdown à chaque
titre ``#`` / ``##`` / ``###`` et on capture la hiérarchie des titres sous
forme de métadonnées.

Passe 2 - récursive avec chevauchement : confiée aux helpers
``splitters`` (``recursive_character_split``).

Mode dialogue : chunks plus larges pour englober une session entière, avec
la liste des locuteurs dans ``metadata["speakers"]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .splitters import (
    hard_split,
    line_speaker,
    recursive_character_split,
    speakers_metadata,
)
from .patterns import strip_kim_chunk_meta

# Taille cible (en caractères) par défaut - Pitch Phase 2.5 : 1000-1500.
DEFAULT_CHUNK_MAX_CHARACTERS = 1200
# Chevauchement par défaut - Pitch Phase 2.5 : 150-200.
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 175
# Taille cible pour les dialogues (sessions entières, contexte préservé).
DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS = 2500
DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS = 250

_HEADING_TITLE_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")

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
            markdown_text = strip_kim_chunk_meta(markdown_text)
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
        return recursive_character_split(
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

        current_size = 0
        for line in lines:
            if not line.strip():
                continue
            speaker = line_speaker(line)
            line_size = len(line) + 1  # +1 pour le saut de ligne.

            # Une ligne de dialogue devenue trop grande (rare) : coupe dure.
            # On vide d'abord le buffer courant, puis la ligne est découpée
            # en morceaux strictement ≤ max_characters (jamais de chunk
            # oversize, jamais de doublon avec la ligne entière), en
            # préservant le locuteur dans les métadonnées.
            if line_size > max_characters:
                if chunk_lines:
                    chunks.append(RAGChunk(
                        chunk_index=len(chunks),
                        content_markdown="\n".join(chunk_lines),
                        metadata=speakers_metadata(per_chunk_speakers),
                    ))
                long_line_speakers = [speaker] if speaker else []
                for piece in hard_split(
                        line, max_characters, overlap_characters):
                    chunks.append(RAGChunk(
                        chunk_index=len(chunks),
                        content_markdown=piece,
                        metadata=speakers_metadata(long_line_speakers),
                    ))
                chunk_lines = []
                per_chunk_speakers = []
                current_size = 0
                continue

            if current_size + line_size > max_characters and chunk_lines:
                chunks.append(RAGChunk(
                    chunk_index=len(chunks),
                    content_markdown="\n".join(chunk_lines),
                    metadata=speakers_metadata(per_chunk_speakers),
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

        if chunk_lines:
            chunks.append(RAGChunk(
                chunk_index=len(chunks),
                content_markdown="\n".join(chunk_lines),
                metadata=speakers_metadata(per_chunk_speakers),
            ))
        return chunks


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