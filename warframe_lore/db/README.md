# Couche `db` — Persistance SQL + RAG

Responsabilité : persister le lore dans **PostgreSQL normalisé** (3NF) armé pour
le RAG, appliquer le **chunking intelligent**, et maintenir le **delta en base**.

Stack : SQLAlchemy 2.0 async + asyncpg + pgvector.

## Contenu

| Fichier / paquet | Rôle |
|---|---|
| `models/` | ORM, un fichier par classe : `base.py`, `wiki_page.py`, `lore_chunk.py`, `kim_dialogue.py`, `game_entity_i18n.py`, `sync_state_record.py` |
| `manager/` | `SQLDatabaseManager` : composition de mixins `base.py` (connexion, `run_ddl_script`), `ingest.py` (upsert page/chunks/dialogues), `entities.py` (upsert `game_entities_i18n`), `delta.py` (état de sync), `queries.py` (stats, récents), `sql_helpers.py` |
| `chunks/` | `ChunkManager` / `RAGChunk` / `chunk_markdown` : découpage Markdown en chunks RAG (`patterns.py` règles KIM, `splitters.py`, `split.py`) |
| `kim_parser.py` | `extract_kim_messages` : extraction des messages KIM depuis les blocs dialogues |

## Schéma (`init_db.sql`)

```
wiki_pages     (page_id PK, namespace, page_title UNIQUE, touched → delta,
                canon_status, content_markdown)
lore_chunks    (id, wiki_page_id FK, chunk_index, content_markdown,
                metadata JSONB, embedding vector(1024))
kim_dialogues  (id, wiki_page_id FK, message_order, speaker, message_text,
                player_choice)
game_entities_i18n (id, entity_id, entity_type, lang, name, description)
sync_state     (bucket_id, page_title PK composite, page_id, touched → delta)
```

Index : `vector(1024)` (pgvector, HNSW), `metadata JSONB` (GIN) pour les filtres
`@>`.

## Chunking RAG (`chunks/`)

Sans dépendance externe (équivalent natif de *langchain-text-splitters*).

**Passe 1 — structurelle** : découpe aux `#`/`##`/`###` ; la hiérarchie devient
`metadata = {"Header 1": …, "Header 2": …}`.

**Passe 2 — récursive** : merge des blocs sous la taille cible, séparateurs
priorisés `\n\n` → `. ` → espace, chevauchement borné — jamais de phrase coupée
en plein mot.

**Mode dialogue** (`is_dialogue=True`, buckets KIM/JDR/Quêtes) : chunks plus
larges (2500c) qui regroupent des blocquotes `> **Nom:** …`, avec
`metadata["speakers"]` = interlocuteurs réels du chunk.

| Constante | Défaut |
|---|---|
| `DEFAULT_CHUNK_MAX_CHARACTERS` | 1200 |
| `DEFAULT_CHUNK_OVERLAP_CHARACTERS` | 175 |
| `DEFAULT_DIALOGUE_CHUNK_MAX_CHARACTERS` | 2500 |
| `DEFAULT_DIALOGUE_CHUNK_OVERLAP_CHARACTERS` | 250 |

Le `SQLDatabaseManager` accepte `chunk_max_characters` /
`chunk_overlap_characters` pour surcharger ces bornes.

Requête RAG ciblée :

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata @> '{"Header 2": "Rank 1 - Neutral"}';   -- GIN index
```

Filtre par locuteur :

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata->'speakers' @> '["Amir"]';
```

## Robustesse de l'upsert

- **Delta en base** : comparaison via `touched` de `wiki_pages` / `sync_state`.
- **Page recréée (nouvel id, même titre)** : les anciens chunks/dialogues sont
  nettoyés et la page ré-assignée pour éviter la violation d'unicité sur le
  titre.
- **Transactional** : l'écriture d'une page = une transaction (upsert + chunks
  + dialogues) ; en cas d'erreur, la page est re-traitée au run suivant.
- `run_ddl_script` découpe `init_db.sql` en statements (asyncpg n'accepte pas
  plusieurs commandes dans un statement préparé).

## KIM (`kim_parser.py`)

Le format des pages KIM est un fichier de chat : une ligne par message,
`> **Personnage:** texte`. `extract_kim_messages` en tire une liste structurée
(intervalles de lignes, speaker, contenu) utilisée aussi pour renseigner
`metadata["speakers"]` du chunking dialogue.

## Usage

```python
from warframe_lore.db import SQLDatabaseManager

async def main():
    mgr = SQLDatabaseManager("postgresql+asyncpg://...")
    await mgr.connect()
    await mgr.upsert_cleaned_page(                # page pré-chunkée / dialogue
        page_title="Excalibur", category="Warframes", page_id=123,
        touched="2026-09-05T12:00:00Z", last_updated="2026-09-05T12:00:00Z",
        canon_status="canon", content_markdown="# Excalibur\n...",
        source_url="https://wiki.warframe.com/wiki/Excalibur",
        detect_kim_dialogues=True,
    )
    state = await mgr.fetch_sync_state("Lore_Quetes")   # état delta du bucket
    await mgr.record_fetch("Lore_Quetes", title, page_id, touched)
    await mgr.purge_vanished_pages("Lore_Quetes", live_titles)
    await mgr.close()
```

La commande `cephalon status` utilise `manager.db_stats()` (pages, chunks,
dialogues, canon, dernières dates) et `cephalon recent` utilise
`manager.recent_pages(limit)` (dernières pages modifiées).