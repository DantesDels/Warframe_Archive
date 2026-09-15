# `db` Layer — SQL Persistence + RAG

Responsibility: persist lore in **normalized PostgreSQL** (3NF) equipped for
RAG, apply **smart chunking**, and maintain the **database-backed delta**.

Stack: SQLAlchemy 2.0 async + asyncpg + pgvector.

## Contents

| File / Package | Role |
|---|---|
| `models/` | ORM, one file per class: `base.py`, `wiki_page.py`, `lore_chunk.py`, `kim_dialogue.py`, `game_entity_i18n.py`, `sync_state_record.py` |
| `manager/` | `SQLDatabaseManager`: mixin composition `base.py` (connection, `run_ddl_script`), `ingest.py` (upsert page/chunks/dialogues), `entities.py` (upsert `game_entities_i18n`), `delta.py` (sync state), `queries.py` (stats, recent), `sql_helpers.py` |
| `chunks/` | `ChunkManager` / `RAGChunk` / `chunk_markdown`: Markdown splitting into RAG chunks (`patterns.py` KIM rules, `splitters.py`, `split.py`) |
| `kim_parser.py` | `extract_kim_messages`: KIM message extraction from dialogue blocks |

## Schema (`warframe_lore/db/init_db.sql`)

```
wiki_pages     (page_id PK, namespace, page_title UNIQUE, touched → delta,
                canon_status, content_markdown)
lore_chunks    (id, wiki_page_id FK, chunk_index, content_markdown,
                metadata JSONB, embedding vector(1024))
kim_dialogues  (id, wiki_page_id FK, message_order, speaker, message_text,
                player_choice)
game_entities_i18n (id, entity_id, entity_type, lang, name, description)
sync_state     (bucket_id, page_title PK composite, page_id, touched → delta)

game_dialogues     (id, wiki_page_id FK, dialogue_kind 'kim'|'cinematic'|'quote',
                    context, chapter, speaker, message_text, player_choice,
                    chemistry_gain, message_order — UNIQUE page+order)
lore_items         (id, wiki_page_id FK, series, item_name, context, planet,
                    narrator, item_text, secret_text, audio — UNIQUE page+name)
warframes          (id, wiki_page_id FK, frame_name, is_prime, description,
                    source_url)
game_quests        (id, wiki_page_id FK, quest_name, quest_type, release_note,
                    quest_context, source_url)
game_updates       (id, wiki_page_id FK, version, update_title, update_type,
                    release_date, platform, summary, source_url)
game_announcements (id, wiki_page_id FK, title, subtitle, published_at,
                    summary, source_url)
```

Indexes: `vector(1024)` (pgvector, HNSW), `metadata JSONB` (GIN) for `@>`
filters.

## RAG Chunking (`chunks/`)

Without external dependencies (a native equivalent of *langchain-text-splitters*).

**Pass 1 — structural**: splits at `#`/`##`/`###`; hierarchy becomes
`metadata = {"Header 1": …, "Header 2": …}`.

**Pass 2 — recursive**: merge of blocks under the target size, prioritized
separators `\n\n` → `. ` → space, bounded overlap — never a sentence cut
mid-word.

**Dialogue mode** (`is_dialogue=True`, KIM/RPG/Quest buckets): larger chunks
(2500c) that group `> **Name:** …` blockquotes, with
`metadata["speakers"]` = actual speakers in the chunk.

| Constant | Default |
|---|---|
| `DEFAULT_CHUNK_MAX_CHARACTERS` | 1200 |
| `DEFAULT_CHUNK_OVERLAP_CHARACTERS` | 175 |
| `DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS` | 2500 |
| `DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS` | 250 |

The `SQLDatabaseManager` accepts `chunk_max_characters` /
`chunk_overlap_characters` to override these bounds.

Targeted RAG query:

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata @> '{"Header 2": "Rank 1 - Neutral"}';   -- GIN index
```

Speaker filter:

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata->'speakers' @> '["Amir"]';
```

## Upsert Robustness

- **Database-backed delta**: comparison via `touched` from `wiki_pages` /
  `sync_state`.
- **Recreated page (new id, same title)**: old chunks/dialogues are cleaned
  up and the page is re-assigned to avoid unique constraint violation on the
  title.
- **Transactional**: writing a page = one transaction (upsert + chunks +
  dialogues); on error, the page is reprocessed on the next run.
- `run_ddl_script` splits `init_db.sql` into statements (asyncpg does not
  accept multiple commands in a prepared statement).

## KIM (`kim_parser.py`)

The KIM page format is a chat file: one line per message,
`> **Character:** text`. `extract_kim_messages` produces a structured list
(line ranges, speaker, content) also used to populate
`metadata["speakers"]` for dialogue-mode chunking.

## Refreshing the database

How to (re)create or (re)populate the schema and data, in order:

| Step | Command | Purpose |
|---|---|---|
| 1. Start the database | `docker compose up -d` | PostgreSQL 16 + pgvector (root `docker-compose.yml`) |
| 2. Create / update the schema | `cephalon init-db` | applies `warframe_lore/db/init_db.sql` (`CREATE TABLE IF NOT EXISTS`); run once per new table or schema change |
| 3. Ingest wiki content | `cephalon run` | fills `wiki_pages` / `lore_chunks` and regenerates the `out/Lore_*.json` megafiles |
| 4. Derive the six element tables | `python -m warframe_lore.structured.pipeline` | populates `game_dialogues`, `lore_items`, `warframes`, `game_quests`, `game_updates`, `game_announcements` |

**Notes**

- The element pipeline is **idempotent**: each page is refreshed in its own
  `DELETE + INSERT` transaction, so re-running it replaces the previous
  derivation without manual cleanup.
- It only *derives* rows from pages already present in `wiki_pages`
  (foreign-key safety).  A fresh database needs step 3 first; without it the
  pipeline logs `Skip … page id … absent from wiki_pages` for every page.
- In PowerShell an exit code of 1 is expected (logs go to stderr); check the
  `INFO … Inserted <table>: N row(s).` lines for the result.
- To re-derive only the element tables (without a full ENGRAM re-run), run
  step 4 alone — the parser content comes from the already-cached megafiles.

## Usage

```python
from warframe_lore.db import SQLDatabaseManager

async def main():
    mgr = SQLDatabaseManager("postgresql+asyncpg://...")
    await mgr.connect()
    await mgr.upsert_cleaned_page(                # pre-chunked / dialogue page
        page_title="Excalibur", category="Warframes", page_id=123,
        touched="2026-09-05T12:00:00Z", last_updated="2026-09-05T12:00:00Z",
        canon_status="canon", content_markdown="# Excalibur\n...",
        source_url="https://wiki.warframe.com/wiki/Excalibur",
        detect_kim_dialogues=True,
    )
    state = await mgr.fetch_sync_state("Lore_Quetes")   # bucket delta state
    await mgr.record_fetch("Lore_Quetes", title, page_id, touched)
    await mgr.purge_vanished_pages("Lore_Quetes", live_titles)
    await mgr.close()
```

The `cephalon status` command uses `manager.db_stats()` (pages, chunks,
dialogues, canon, latest dates) and `cephalon recent` uses
`manager.recent_pages(limit)` (latest modified pages).
