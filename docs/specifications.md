# System Specifications & Requirements — Cephalon Archive

> Formal specifications, operational constraints and technical requirements for the Warframe knowledge pipeline.

---

## 1. Functional Specifications

| Ref | Domain | Need | Expected Behavior |
|---|---|---|---|
| **FR-1** | Scraping | Collection | Scraping of MediaWiki wiki (`wiki.warframe.com`) by **category buckets** (8 default buckets, recursive sub-categories, title filters); **incremental delta** update (only modified pages are reprocessed); `--force` to reprocess everything. |
| **FR-2** | Cleaning | Wikitext Normalization | Wikitext → Markdown conversion: removal of noise, gameplay sections, dialogue normalization into `> **Speaker:** text` blocks; rules externalized in `config/cleaner_config.json`. |
| **FR-3** | Canon | Canon Level Detection | Each entry carries `canon_status` (`canon` / `speculation` / `community_theory`) detected via `Category:Speculation` and inline templates (`{{Speculation}}`, `{{Canon}}`); merge to the most cautious status. |
| **FR-4** | Storage | Parallel Persistence | **Parallel** output: JSON megafiles per bucket (`out/*.json`) **and** 3NF PostgreSQL (`wiki_pages`, `lore_chunks` + JSONB `metadata` + `embedding vector(1024)`, `kim_dialogues`, `game_entities_i18n`, `sync_state_records`). Two-pass RAG chunking integrated at insertion. |
| **FR-5** | Export | Game Entities | Import of **localized entities** from the official Public Export (`origin.warframe.com`) → `game_entities_i18n`, join on official `entity_id` (never on a translated name). |
| **FR-6** | Datamine | KIM Mirror | Datamine of KIM conversations (`*.dialogue.json` + localization dictionaries) → strict tree graphs, message list, first-branch script, choice simulator, unique `root` system node. |
| **FR-7** | Web UI | Local Inspection | Read-only local HTTP server for megafiles: overview, bucket browser, KIM dialogues, recent, full-text search, media. Gzip responses; no network access at runtime (except on-demand images). |
| **FR-8** | RAG | Document QA | `POST /v1/rag {question, stream?}` → anchored response **+ sources** (title, excerpt, score). Name aliases (`lettie → Leticia`), disambiguation "Did you mean …?", **short-circuit** if no passage above the threshold (the LLM is not called: exact error chain, empty sources). |
| **FR-9** | Roleplay | WebSocket Terminal | `WS /v1/roleplay`: token-by-token streaming, session per connection, sliding memory window (turn bounds + characters), editable persona (`persona/oracle`). Flag `rag` to anchor a turn on the archives. |
| **FR-10** | Discord | Loremaster Oracle | "Loremaster Oracle" bot: live token broadcast (message edits), lore question detection (lexical triggers) → RAG flag, automatic reconnection on dead stream, channel restriction, **matriciel member cards** (real Discord roles, ID, security level, assiduité/fiabilité, behavioural analysis), creator-gated access, persistent member activity, and **narrative tales**: story requests ("raconte-moi l'histoire de …") open a targeted lore dossier told in French through double-pass draft+narration with lens/era doors and pagination. |

---

## 2. Non-Functional Specifications

| Ref | Category | Requirement | Implementation |
|---|---|---|---|
| **NFR-1** | Fidelity | Zero Fabrication | Strict abstention: short-circuit on low scores, entity absence guard, and unified error protocols. The LLM is never invoked without verified evidence. |
| **NFR-2** | Performance | Fast Latency | Near-instant TTFT (streaming); complete RAG response typically < 10-30 s on 8 GB VRAM; short-circuit ~0.5 s; network politeness 0.4 s per API call. |
| **NFR-3** | Resources | 8 GB VRAM Budget | Fits strictly within **8 GB VRAM**: `top_k = 3` (~1,000-1,500 tokens), `max_context_chars = 4500`, `max_tokens = 2048`, quantized Q4_K_M chat model (~5 GB). |
| **NFR-4** | Robustness | Fault-Tolerance | HTTP retries/exponential backoff, atomic JSON publications, replayable delta, Discord reconnection < 1 s (tested), `restart: unless-stopped` for the database. |
| **NFR-5** | Security | 100% Local Execution | Everything runs **locally** (dummy API key `lm-studio`, servers on `127.0.0.1`); no secrets committed in the repository (Discord token via environment). |
| **NFR-6** | Maintainability | SOLID & Dependency Inversion | Injected protocols (`Retriever`, `LLMProvider`, `EmbeddingProvider`), environment-based configuration, strict rules of coding (≤ 100 LOC, ≤ 15 files). |
| **NFR-7** | Testability | Continuous Verification | Full green unit test suite (832 tests); data audit tools; automated linter (`ruff`) and static bytecode compilation (`compileall`). |
| **NFR-8** | Safety | Fictional Lore Context | Lore deals with dark subjects (cloning, experiments…): the model is explicitly authorized to describe them via a "SECURITY CONTEXT" system prompt block. |

---

## 3. Operational Requirements

### Hardware
- **GPU (Inference)**: Minimum 8 GB VRAM (`Gemma-2-9b-it` Q4_K_M ~5 GB; or `Llama-3.2-3B` ~2 GB).
- **RAM**: Minimum 16 GB, 32 GB recommended.
- **Storage**: ~5-10 GB for megafiles, media caches, and PostgreSQL pgvector volume.
- **Operating System**: Windows 10/11 or Linux (Docker).

### Software & Services
- **Python**: $\ge 3.11$ (tested on 3.12).
- **PostgreSQL 16 + `pgvector`**: via Docker (`pgvector/pgvector:pg16`).
- **LM Studio**: Exposing an OpenAI-compatible endpoint on `http://127.0.0.1:1234/v1` with:
  - Chat: `gemma-2-9b-it` (GGUF, Q4_K_M)
  - Embedding: `text-embedding-baai-bge-m3-568m` (GGUF, 1024d)

