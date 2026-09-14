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
| `rag/` | `retriever.py` (`Retriever` contract + `RAGHit`), `search.py` (`CosinusSearch` pgvector), `prompt.py` (`PromptBuilder`), `service.py` (`RAGService`) |
| `roleplay/` | `models.py` (`Session`/`Turn`), `turn.py` (`plan_turn` — deterministic short-circuits BEFORE the LLM: probe, missing archives, guild member, speaker identity), `stream.py` (`RoleplayService` streaming), `prompt/` (`blocks.py` BLOC 1 + directives de fin, `directives.py` fiche interlocuteur / civilité / jalousie / langue, `window.py` `SlidingWindow`), `replies/` (`identity.py` deterministic speaker-identity + member-card replies, `comment.py` one-shot member observation), `memory.py` (`UserMemoryStore`) |
| `api/` | `main.py` (FastAPI), `container.py` (service composition), `schemas.py` (HTTP), `routers/` (`document_rag.py`, `roleplay.py` WS terminal — transport only, `roleplay_stream.py` frame emission) |
| `scripts/` | `ingest.py`: ETL from JSON megafiles → vectorized `lore_chunks` |

## Architecture

```
EngramConfig ──► Container (DI) ──┬─► LMStudioProvider (chat + embed)
                                  ├─► CosinusSearch (Retriever pgvector)
                                  ├─► RAGService  → POST /v1/rag
                                  └─► RoleplayService → WS /v1/roleplay
```

The engine (`RAGService`) depends only on `EmbeddingProvider`, `Retriever`
and `LLMProvider` abstractions (dependency inversion) — you can plug in
another vector store (FAISS, Qdrant…) or another LLM without touching the
core.

## Document RAG

1. The question is vectorized (`bge-m3`, 1024d) via LM Studio;
2. `CosinusSearch` queries `lore_chunks.embedding` by cosine similarity
   pgvector (operator `<=>`, HNSW index), limited by `top_k` + `min_score`;
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
inherently fictional. `max_tokens` default 4096 (exhaustive Codex files are
not truncated).

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

## Installation / Launch

```bash
# PostgreSQL + pgvector database (docker-compose root)
docker compose up -d

# Schema + ingestion + vectorization
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

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
