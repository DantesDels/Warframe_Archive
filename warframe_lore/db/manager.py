"""Gestionnaire de base de données SQL (SQLAlchemy 2.0 + asyncpg).

``SQLDatabaseManager`` remplace la logique purement JSON pour la persistance
relationnelle : il écrit les pages nettoyées dans PostgreSQL (upsert
transactionnel), en parallèle des megafiles JSON.

C'est aussi ici que vit le nouveau suivi du mode delta : ``sync_state`` en
base remplace (à terme) le ``sync_state.json`` local.  La comparaison se
fait sur le champ ``touched`` renvoyé par l'API wiki.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from ..output.models import CanonStatus
from .chunker import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
)
from .kim_parser import extract_kim_messages
from .models import (
    Base,
    GameEntityI18n,
    KimDialogue,
    LoreChunk,
    SyncStateRecord,
    WikiPage,
)

log = logging.getLogger("warframe_lore.db")


class SQLDatabaseManager:
    """Point d'entrée de la couche SQL (async).

    Args:
        database_url: URL PostgreSQL async (ex:
            ``postgresql+asyncpg://user:password@host:5432/warframe_lore``).
        chunk_max_characters: taille max d'un chunk ``lore_chunks``
            (Phase 2.5 : cible 1000-1500).
        chunk_overlap_characters: chevauchement entre chunks consécutifs
            (Phase 2.5 : cible 150-200).
    """

    def __init__(self, database_url: str,
                 chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
                 chunk_overlap_characters: int = (
                     DEFAULT_CHUNK_OVERLAP_CHARACTERS)) -> None:
        self.database_url = database_url
        self.chunk_max_characters = chunk_max_characters
        self.chunk_overlap_characters = chunk_overlap_characters
        # ChunkManager Phase 2.5 : découpage structurel + récursif + dialogue.
        self.chunker = ChunkManager(
            chunk_max_characters=chunk_max_characters,
            chunk_overlap_characters=chunk_overlap_characters,
        )
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Crée l'engine async et vérifie la connexion."""
        self._engine = create_async_engine(self.database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False)
        async with self._engine.connect() as connection:
            await connection.execute(select(1))
        log.info("Connecté à PostgreSQL (%s)", self.database_url.split("@")[-1])

    async def close(self) -> None:
        """Ferme proprement le pool de connexions."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def run_ddl_script(self, sql_script_path) -> None:
        """Exécute un script SQL (DDL, ex: ``init_db.sql``) via asyncpg.

        asyncpg (via SQLAlchemy) ne permet pas plusieurs commandes dans un
        statement préparé => on découpe le script en statements individuels.
        Chaque statement est exécuté dans la même transaction.
        """
        self._require_session_factory()
        assert self._engine is not None
        script_sql = await asyncio.to_thread(
            Path(sql_script_path).read_text, encoding="utf-8")
        statements = _split_sql_statements(script_sql)
        async with self._engine.begin() as connection:
            for sql_statement in statements:
                await connection.exec_driver_sql(sql_statement)
        log.info("Script DDL exécuté : %s (%d statement(s))",
                 sql_script_path, len(statements))

    def _require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError(
                "SQLDatabaseManager non connecté : appelez connect() d'abord.")
        return self._session_factory

    # --------------------------------------------------------- upsert page
    async def upsert_cleaned_page(
        self,
        *,
        page_title: str,
        category: str,
        page_id: int,
        touched: str | None,
        last_updated: str | None,
        canon_status: CanonStatus | str,
        content_markdown: str,
        source_url: str = "",
        namespace: int = 0,
        detect_kim_dialogues: bool = True,
    ) -> None:
        """Upsert transactionnel d'une page nettoyée + ses chunks.

        Une page à l'état ``PageData`` nettoyé devient :
          * 1 ligne ``wiki_pages`` (Insert ou Update selon existence) ;
          * N lignes ``lore_chunks`` (remplacées atomiquement) ;
          * M lignes ``kim_dialogues`` si la page contient du dialogue KIM.

        Le tout dans une seule transaction : en cas d'échec, rien n'est
        partiellement persisté.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                # --- 1. Upsert de la page racine.
                # PostgreSQL : INSERT ... ON CONFLICT DO UPDATE (requis par le
                # cahier des charges).  Autre dialecte (SQLite/tests) : repli
                # "read-then-write" portatif.
                await self._upsert_wiki_page(session, WikiPage(
                    page_id=page_id,
                    page_title=page_title,
                    category=category,
                    namespace=namespace,
                    touched=touched,
                    last_updated=_parse_timestamp(last_updated),
                    canon_status=_as_canon_status_string(canon_status),
                    source_url=source_url,
                    content_markdown=content_markdown,
                ))

                # --- 2. Remplacement des chunks : DELETE + INSERT.
                await session.execute(
                    delete(LoreChunk).where(LoreChunk.wiki_page_id == page_id))
                rag_chunks = self.chunker.split(
                    content_markdown,
                    is_dialogue=detect_kim_dialogues,
                )
                for chunk in rag_chunks:
                    session.add(LoreChunk(
                        wiki_page_id=page_id,
                        chunk_index=chunk.chunk_index,
                        content_markdown=chunk.content_markdown,
                        chunk_metadata=chunk.metadata,
                    ))

                # --- 3. Dialogues KIM (si détectés).
                kim_message_count = 0
                if detect_kim_dialogues:
                    await session.execute(
                        delete(KimDialogue).where(
                            KimDialogue.wiki_page_id == page_id))
                    messages = extract_kim_messages(content_markdown)
                    kim_message_count = len(messages)
                    for message in messages:
                        session.add(KimDialogue(
                            wiki_page_id=page_id,
                            message_order=message.message_order,
                            speaker=message.speaker,
                            message_text=message.message_text,
                            player_choice=message.player_choice,
                            timestamp=message.timestamp,
                        ))

            log.debug("Upsert terminé pour '%s' (page_id=%d, %d chunks, %d KIM)",
                      page_title, page_id, len(rag_chunks), kim_message_count)
        # NB: afin de rendre le log lisible en cas de page sans dialogue.
        if not content_markdown.strip():
            log.debug("Page '%s' sans contenu nettoyé (ignorée).", page_title)

    # --------------------------------------------------------- entités i18n
    async def upsert_game_entities(
        self, entities: list[tuple[str, str | None, str, str, str | None]],
    ) -> int:
        """Upsert d'entités localisées dans ``game_entities_i18n``.

        Args:
            entities: tuples ``(entity_id, entity_type, lang, name, description)``.
                L'upsert se fait sur ``(entity_id, lang)`` — mise à jour du nom,
                de la description et refresh de ``updated_at``.

        Returns:
            Nombre de lignes upsertées.
        """
        if not entities:
            return 0
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                written = 0
                # asyncpg plafonne le nombre de paramètres par requête (32767).
                # 5 colonnes/ligne -> lots de 2500 lignes (12500 params).
                for start in range(0, len(entities), 2500):
                    batch = entities[start:start + 2500]
                    payload = [
                        {
                            "entity_id": entity_id,
                            "entity_type": entity_type,
                            "lang": lang,
                            "name": name,
                            "description": description,
                        }
                        for entity_id, entity_type, lang, name, description in batch
                    ]
                    statement = pg_insert(GameEntityI18n).values(payload)
                    statement = statement.on_conflict_do_update(
                        index_elements=["entity_id", "lang"],
                        set_={
                            "entity_type": statement.excluded.entity_type,
                            "name": statement.excluded.name,
                            "description": statement.excluded.description,
                            "updated_at": func.now(),
                        },
                    )
                    result = await session.execute(statement)
                    written += result.rowcount or len(payload)
        return written

    # --------------------------------------------------------- entités i18n
    async def count_game_entities(self) -> tuple[int, set[str]]:
        """Stats : nombre de lignes et langues présentes (diagnostic)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            langs = set((await session.execute(
                select(GameEntityI18n.lang).distinct())).scalars().all())
            total = (await session.execute(
                select(func.count()).select_from(GameEntityI18n))).scalar() or 0
            return total, langs

    # --------------------------------------------------------- mode delta
    async def fetch_sync_state(self, bucket_id: str) -> dict[str, dict[str, Any]]:
        """Retourne ``{titre: {pageid, touched}}`` pour un bucket (delta).

        Les pages en base pour ce bucket servent de référence : seule une
        différence de ``touched`` déclenche un re-téléchargement.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            records = await session.execute(
                select(SyncStateRecord).where(
                    SyncStateRecord.bucket_id == bucket_id))
            return {record.page_title: {
                "pageid": record.page_id,
                "touched": record.touched or "",
            } for record in records.scalars()}

    async def record_fetch(self, bucket_id: str, page_title: str,
                           page_id: int, touched: str | None) -> None:
        """Marque une page comme synchronisée (upsert dans ``sync_state``)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                existing = await session.get(
                    SyncStateRecord, (bucket_id, page_title))
                if existing is None:
                    session.add(SyncStateRecord(
                        bucket_id=bucket_id,
                        page_title=page_title,
                        page_id=page_id,
                        touched=touched or "",
                    ))
                else:
                    existing.page_id = page_id
                    existing.touched = touched or ""
                    existing.updated_at = datetime.now()

    async def purge_vanished_pages(self, bucket_id: str,
                                   live_titles: set[str]) -> None:
        """Efface de l'état les pages disparues de la catégorie résolue."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(SyncStateRecord).where(
                        SyncStateRecord.bucket_id == bucket_id,
                        SyncStateRecord.page_title.not_in(list(live_titles))
                        if live_titles else True))

    # ------------------------------------------------------------- helpers
    async def _upsert_wiki_page(self, session: AsyncSession,
                                page_record: WikiPage) -> None:
        """Upsert d'une page ``wiki_pages`` adapté au dialecte SQL.

        PostgreSQL : ``INSERT ... ON CONFLICT (page_id) DO UPDATE``.
        Autres dialectes (SQLite pour tests) : lecture puis insert/update.

        Robuste aux pages recréées sur le wiki (même ``page_title`` mais
        nouveau ``page_id``) : l'ancienne occurrence est d'abord écartée
        (cascade : chunks + dialogues) pour ne pas violer l'index unique
        ``idx_wiki_pages_title``.
        """
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            # --- 0. Réassignation de sécurité (page recréée sur le wiki).
            same_title_ids = (await session.execute(
                select(WikiPage.page_id).where(
                    WikiPage.page_title == page_record.page_title))).scalars().all()
            for stale_id in same_title_ids:
                if stale_id != page_record.page_id:
                    await session.execute(
                        delete(LoreChunk).where(LoreChunk.wiki_page_id == stale_id))
                    await session.execute(
                        delete(KimDialogue).where(KimDialogue.wiki_page_id == stale_id))
                    stale_page = await session.get(WikiPage, stale_id)
                    if stale_page is not None:
                        await session.delete(stale_page)

            statement = pg_insert(WikiPage).values(
                page_id=page_record.page_id,
                page_title=page_record.page_title,
                category=page_record.category,
                namespace=page_record.namespace,
                touched=page_record.touched,
                last_updated=page_record.last_updated,
                canon_status=page_record.canon_status,
                source_url=page_record.source_url,
                content_markdown=page_record.content_markdown,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[WikiPage.page_id],
                set_={
                    "page_title": statement.excluded.page_title,
                    "category": statement.excluded.category,
                    "namespace": statement.excluded.namespace,
                    "touched": statement.excluded.touched,
                    "last_updated": statement.excluded.last_updated,
                    "canon_status": statement.excluded.canon_status,
                    "source_url": statement.excluded.source_url,
                    "content_markdown": statement.excluded.content_markdown,
                    "updated_at": func.now(),
                },
            )
            await session.execute(statement)
        else:
            existing_page = await session.get(WikiPage, page_record.page_id)
            if existing_page is None:
                session.add(page_record)
            else:
                existing_page.page_title = page_record.page_title
                existing_page.category = page_record.category
                existing_page.namespace = page_record.namespace
                existing_page.touched = page_record.touched
                existing_page.last_updated = page_record.last_updated
                existing_page.canon_status = page_record.canon_status
                existing_page.source_url = page_record.source_url
                existing_page.content_markdown = page_record.content_markdown
                existing_page.updated_at = datetime.now()

    async def count_pages(self) -> int:
        """Nombre total de pages en base (diagnostic / tests)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(WikiPage))
            return len(result.scalars().all())

    # -------------------------------------------------------------- stats
    async def db_stats(self) -> dict[str, Any]:
        """Indicateurs de l'état de la base (diagnostic ``cephalon status``).

        Retourne :
            ``total_pages``, ``total_chunks``, ``total_kim_dialogues``,
            ``total_sync_records``, ``total_by_canon``, ``pages_by_bucket``,
            ``last_page_updated``, ``last_sync_at``.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            total_pages = (await session.execute(
                select(func.count()).select_from(WikiPage))).scalar_one()
            total_chunks = (await session.execute(
                select(func.count()).select_from(LoreChunk))).scalar_one()
            total_kim = (await session.execute(
                select(func.count()).select_from(KimDialogue))).scalar_one()
            total_sync = (await session.execute(
                select(func.count()).select_from(SyncStateRecord))).scalar_one()

            canon_rows = (await session.execute(
                select(WikiPage.canon_status, func.count()).group_by(
                    WikiPage.canon_status))).all()
            total_by_canon = {status: count for status, count in canon_rows}

            bucket_rows = (await session.execute(
                select(WikiPage.category, func.count()).group_by(
                    WikiPage.category))).all()
            pages_by_bucket = {name: count for name, count in bucket_rows}

            last_page_updated = (await session.execute(
                select(func.max(WikiPage.created_at)))).scalar_one()
            last_page_touched = (await session.execute(
                select(func.max(WikiPage.updated_at)))).scalar_one()
            last_sync_at = (await session.execute(
                select(func.max(SyncStateRecord.updated_at)))).scalar_one()

        return {
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "total_kim_dialogues": total_kim,
            "total_sync_records": total_sync,
            "total_by_canon": total_by_canon,
            "pages_by_bucket": pages_by_bucket,
            "last_page_created_at": last_page_updated,
            "last_page_updated_at": last_page_touched,
            "last_sync_at": last_sync_at,
        }

    async def recent_pages(self, limit: int = 10) -> list[dict[str, Any]]:
        """Dernières pages modifiées (``cephalon recent``).

        Tri par ``updated_at`` décroissant ; inclut titre, catégorie,
        statut canon, dates.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            rows = await session.execute(
                select(WikiPage).order_by(
                    WikiPage.updated_at.desc(),
                    WikiPage.created_at.desc(),
                ).limit(limit))
            return [
                {
                    "page_title": p.page_title,
                    "category": p.category,
                    "canon_status": p.canon_status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                }
                for p in rows.scalars().all()
            ]


def _parse_timestamp(value: str | None) -> Optional[datetime]:
    """Convertit un timestamp ISO en datetime (None si invalide).

    Le champ ``touched`` de l'API wiki est de la forme
    ``2026-09-05T16:20:11Z`` (suffixe Z = UTC).
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_canon_status_string(canon_status: CanonStatus | str) -> str:
    """Normalise un statut canon en sa valeur string."""
    if isinstance(canon_status, CanonStatus):
        return canon_status.value
    return canon_status


def _split_sql_statements(sql_script: str) -> list[str]:
    """Découpe un script SQL en statements individuels.

    asyncpg interdit plusieurs commandes dans un statement préparé : on
    scinde sur les points-virgules hors chaînes de caractères, et on ignore
    les commentaires ``-- ...`` (qui peuvent contenir des apostrophes).
    """
    statements: list[str] = []
    current_statement: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    line_length = len(sql_script)

    while index < line_length:
        character = sql_script[index]
        next_character = sql_script[index + 1] if index + 1 < line_length else ""

        # Commentaire SQL '--' hors chaîne : on saute jusqu'au saut de ligne.
        if character == "-" and next_character == "-" \
                and not in_single_quote and not in_double_quote:
            while index < line_length and sql_script[index] != "\n":
                index += 1
            continue

        if character == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif character == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        current_statement.append(character)
        if character == ";" and not in_single_quote and not in_double_quote:
            statement_text = "".join(current_statement).strip()
            if statement_text:
                statements.append(statement_text)
            current_statement = []
        index += 1

    trailing_statement = "".join(current_statement).strip()
    if trailing_statement:
        statements.append(trailing_statement)
    return statements