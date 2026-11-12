# `engram` Layer — AI Backend & RAG

Responsibility: expose the vectorized knowledge base and a real-time
Roleplay terminal, backed by a **local LM Studio** (chat + embedding).

Designed in strict compliance with SOLID (one role per module, interfaces
injected via dependency inversion): the `API` never depends on concrete
storage or clients — it consumes abstractions injected via the `Container`.

## Contents

| File / Package | Role |
|---|---|
| `config.py` | `EngramConfig`: DB/LLM URLs, models, top_k, windows (overridable via `ENGRAM_*` env vars) |
| `persona.py` | `Persona`: system prompt read from `persona/oracle` (editable on the fly) |
| `llm/` | `base.py` (`LLMProvider` / `EmbeddingProvider` interfaces), `lmstudio.py` (`LMStudioProvider`, OpenAI-compatible) |
| `rag/` | `retriever.py` (`Retriever` contract + `RAGHit`), `search.py` (facade `CosinusSearch` pgvector — `_build_statement`/`suggest_title`/dossier delegations, re-exports `DOSSIER_LIMIT`, `set_hnsw_ef_search`, `dossier_title_terms`), `dossier.py` (`lore_dossier_statement` story-first tiers + `DOSSIER_LIMIT`), `suggestion.py` (lexical title suggestion), `hnsw.py` (session `ef_search` tuning), `structured_search.py` (`StructuredSearch` on the six element tables), `hybrid.py` (`HybridSearch` vector + FTS), `merged.py` (`MergedRetriever`), `prompt.py` (`PromptBuilder`), `verify.py` (`verify_answer` — deterministic post-generation entity gate, `lexeme_forms` accent/number/gender variants), `service.py` (`RAGService`), `scoring.py` (`query_terms`, `ts_rank_normalized`), `model.py` (hit dataclasses), `vocabulary.py` (`ArchiveVocabulary` — whole-corpus vocabulary behind the post-generation gate, probing those same variants) |
| `roleplay/` | `models.py` (`Session`/`Turn`), `turn.py` (`plan_turn` — deterministic short-circuits BEFORE the LLM: probe, missing archives, guild member, speaker identity), `stream.py` (orchestrator `RoleplayService` streaming), `story_turn.py` (story double pass: invisible factual draft then narration system, KIM messenger directive), `verify_gate.py` (post-generation gate: archive verification + mandated part closing), `purge.py` (canonical story closings), `prompt/` (`blocks.py` BLOC 1 + directives de fin, `directives.py` fiche interlocuteur / civilité / jalousie / langue, `narrative.py` story/lens/targeted-era directives, `window.py` `SlidingWindow`), `replies/` (`identity.py` deterministic speaker-identity + member-card replies, `comment.py` one-shot member observation), `memory.py` (`UserMemoryStore`) |
| `api/` | `main.py` (FastAPI), `container.py` (service composition), `schemas.py` (HTTP), `routers/` (`document_rag.py`, `roleplay.py` WS terminal — transport only, `roleplay_stream.py` frame emission) |
| `scripts/` | `ingest.py`: ETL from JSON megafiles → vectorized `lore_chunks`; `embed_structured.py`: embed the six element tables → `structured_chunks` |

## Architecture

```
EngramConfig ──► Container (DI) ──┬─► LMStudioProvider (chat + embed)
                                  ├─► MergedRetriever ─┬─► CosinusSearch (lore_chunks pgvector)
                                  │                    └─► StructuredSearch (structured_chunks pgvector)
                                  ├─► RAGService  → POST /v1/rag
                                  └─► RoleplayService → WS /v1/roleplay
```

The engine (`RAGService`) depends only on `EmbeddingProvider`, `Retriever`
and `LLMProvider` abstractions (dependency inversion) — you can plug in
another vector store (FAISS, Qdrant…) or another LLM without touching the
core.

## Document RAG

1. The question is vectorized (`bge-m3`, 1024d) via LM Studio;
2. `MergedRetriever` runs BOTH channels in parallel — `CosinusSearch`
   queries `lore_chunks.embedding` by cosine similarity pgvector (operator
   `<=>`, HNSW index) and `StructuredSearch` queries `structured_chunks`
   (the embedded six element tables: warframes, quests, updates,
   announcements, lore items, dialogues) — merged by score, capped at
   `top_k`;
3. `PromptBuilder` assembles **a single XML-strict system message**: persona,
   `<archives>{context}</archives>` tags and fixed fallback directives
   (Gemma-2 better delimits internal knowledge / context / instructions
   when everything is in a single block). Capped at `top_k=3` passages and
   ~4500 characters (≤1500 tokens);
4. The LLM generates the response, streamed or in one shot, with sources.
   **Temperature 0.1** (analytical). No passage above the threshold →
   **short-circuit**: the LLM is not called, the exact mnemonic error string
   is returned.

**Anti-hallucination guards** (in addition to the relevance threshold):
- **Entity-lookup guard** — a "qui est X / qu'est-ce que X / parle-moi de X"
  question whose proper-noun target never appears in the retrieved passages
  short-circuits: the model never fabricates a biography (playtest
  "Qui est Vena ?").
- Alias middleware applied **before** vectorization; relevance fallback
  directive (#5) and strict rejection format (#6) in the prompt; output
  sanitization (`strip_trailing_padding`).

Model `Gemma-2-9b-it` (gguf Q4_K_M, ~5 GB VRAM): `stream=True` streaming,
visible content filter only (`delta.content`), **low temperature** (0.3 in
free chat, 0.1 on RAG routes) for faithful responses and near-instant TTFT.
A **fiction bypass** ("SECURITY CONTEXT" prompt block) lifts Gemma's ethical
filters: Warframe lore deals with cloning, experiments and rituals that are
inherently fictional. `max_tokens` default 2048: gemma-2 tops out at 8192
tokens and the assembled prompt already measures ~5900 (the persona alone is
~4600 of them), so a bigger cap makes the engine answer "Context size has
been exceeded"; a generation that fails is served as the abstention string
(never a 500, never a raw server error).

## Roleplay Terminal (WebSocket)

`WS /v1/roleplay`: one session per connection, `SlidingWindow` bounds the
history (turn count + context size), the LLM responds **token by token**,
the response is recorded in the session after broadcast.

Additional control frame **`comment`**: the Discord bot asks for a one-shot,
non-streamed **behavioural analysis** of a guild member (name, real roles,
recent interactions) — returned as a single `{"type": "comment", "text": …}`
frame, generated with a dedicated directive (no Codex format, factual).

The persona (system prompt) is loaded from `persona/oracle` at startup —
freely editable, then restart the server. It carries the roleplay rules:
Directive Zéro (creator devotion), the anti-préambule / anti-répétition
rules, the **Codex formatting** (`> **◈ ARCHIVE DU CODEX**` lore cards) and
the external-organics / jealousy protocols.

## Targeted Stories (Lore Dossier)

A story request ("raconte-moi l'histoire de X") grounds the narrative on the
subject's OWN pages instead of the nearest semantic neighbors — the pure
`top_k` search ranks first-person KIM dialogues above the biography
(playtest "l'histoire d'Eleanor": Background landed at rank ~16).

- **Dossier SQL** (`retrieval/dossier.py`, `DOSSIER_LIMIT = 12`): the exact
  biography page first (tier 0), its French mirror, then child pages
  (`Eleanor/Quotes`, tier 1), then title-matching pages and finally
  content-only mentions — in narrative reading order. `exclude_ids` is the
  only cursor the server trusts (chunks already narrated are banned in SQL);
  one chunk is fetched beyond the window to know whether anything is left.
- **Alias sweep** (`query/aliases.py::dossier_title_terms`): the subject key
  (`lettie`) expands to its canonical title (`Leticia`) so the biography page
  keeps its tier-0 slot (Lettie playtest).
- **Story double pass** (`roleplay/story_turn.py`): two LLM calls — an
  invisible French-only factual draft (cold, 0.1), then the narration system
  (lens/targeted-era directive + draft, French locks). The **KIM messenger
  directive** teaches the model that `KIM · …` excerpts are Hex messages, KIM
  is a TOOL and never a character.
- **Emission gate** (`api/routers/roleplay_stream.py`): a degenerate part
  (empty text or closing sentence alone) is never served — the turn is
  re-planned past the dead window; with unseen fragments the honest `RAG_ERROR`
  abstention keeps `story_more = True`, a drained dossier ends with the
  archivist stop.

## Installation / Launch

```bash
# PostgreSQL + pgvector database (docker-compose root)
docker compose up -d

# Schema + ingestion + vectorization
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

# Embed the six human-readable element tables
python -m warframe_lore.engram.scripts.embed_structured   # optional --kinds

# API
uvicorn warframe_lore.engram.api.main:app --port 8000
```

Requires LM Studio on `http://localhost:1234` (chat + embedding), models
overridable via `ENGRAM_CHAT_MODEL`, `ENGRAM_EMBED_MODEL`, `ENGRAM_LLM_BASE`.

## Endpoints

| Route | Type | Role |
|---|---|---|
| `/health` | GET | Service status |
| `/v1/rag` | POST | Document RAG (`{question, stream}`) → response + sources |
| `/v1/roleplay` | WS | Oracle terminal, token streaming |
| `/docs`, `/redoc` | GET | Interactive documentation |
