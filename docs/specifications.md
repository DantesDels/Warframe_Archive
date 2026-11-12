# System Specifications & Requirements — Cephalon Archive

> Formal specifications, operational constraints and technical requirements for the Warframe knowledge pipeline.

---

## 1. Functional Specifications

| Ref | Domain | Need | Expected Behavior |
|---|---|---|---|
| **FR-1** | Scraping | Collection | Scraping of MediaWiki wiki (`wiki.warframe.com`) by **category buckets** (16 default buckets, recursive sub-categories, title filters); **incremental delta** update (only modified pages are reprocessed); `--force` to reprocess everything. |
| **FR-2** | Cleaning | Wikitext Normalization | Wikitext → Markdown conversion: removal of noise, gameplay sections, dialogue normalization into `> **Speaker:** text` blocks; rules externalized in `config/cleaner_config.json`. |
| **FR-3** | Canon | Canon Level Detection | Each entry carries `canon_status` (`canon` / `speculation` / `community_theory`) detected via `Category:Speculation` and inline templates (`{{Speculation}}`, `{{Canon}}`); merge to the most cautious status. |
| **FR-4** | Storage | Parallel Persistence | **Parallel** output: JSON megafiles per bucket (`out/*.json`) **and** 3NF PostgreSQL (`wiki_pages`, `lore_chunks` + JSONB `metadata` + `embedding vector(1024)`, `kim_dialogues`, `game_entities_i18n`, `sync_state`). Two-pass RAG chunking integrated at insertion. |
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
| **NFR-7** | Testability | Continuous Verification | Full green unit test suite (834 tests); data audit tools; automated linter (`ruff`) and static bytecode compilation (`compileall`). |
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

---

## 4. Environment Variables

Every setting is overridable by environment variable (no sensitive values in
the repository; the repo ships `config/buckets.json`, `persona/oracle` and
`config/cleaner_config.json`).

### Pipeline (`WF_*`)

| Variable | Default | Role |
|---|---|---|
| `WF_API_URL` | `https://wiki.warframe.com/api.php` | MediaWiki endpoint |
| `WF_OUTPUT_DIR` | `out/` | JSON megafiles + media |
| `WF_STATE_FILE` | `out/state.json` | Delta state (legacy, replaced by the database) |
| `WF_DATABASE_URL` | `postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore` | SQL + pgvector database |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | constants in `warframe_lore/config.py` | Server HTTP policy |

### ENGRAM (`ENGRAM_*`)

| Variable | Default | Role |
|---|---|---|
| `ENGRAM_LLM_BASE` | `http://localhost:1234/v1` | LM Studio OpenAI endpoint |
| `ENGRAM_LLM_KEY` | `lm-studio` | Dummy API key (everything is local) |
| `ENGRAM_CHAT_MODEL` | `gemma-2-9b-it` | Chat model |
| `ENGRAM_CHAT_TEMP` | `0.3` | Free chat temperature |
| `ENGRAM_MAX_TOKENS` | `2048` | Generation bound |
| `ENGRAM_EMBED_MODEL` | `text-embedding-baai-bge-m3-568m` | Embeddings |
| `ENGRAM_EMBED_DIM` | `1024` | Vector dimension (HNSW index) |
| `ENGRAM_TOP_K` | `3` | Returned neighbours |
| `ENGRAM_MIN_SCORE` | `0.35` | Confidence threshold (context provided) |
| `ENGRAM_SUGGEST_MIN_SCORE` | `0.5` | Disambiguation threshold "Did you mean…?" |
| `ENGRAM_CRITICAL_MIN_SCORE` | `0.5` | **Critical threshold**: below this score the LLM is never called (short-circuit) |
| `ENGRAM_MAX_TURNS` | `20` | Roleplay memory window (turns) |
| `ENGRAM_MAX_CTX_CHARS` | `4500` | Roleplay memory window (characters) |

### Discord bot (`DISCORD_*`)

| Variable | Default | Role |
|---|---|---|
| `DISCORD_TOKEN` | *(empty)* | Bot secret token (required) |
| `ENGRAM_WS_URL` | `ws://localhost:8000/v1/roleplay` | Oracle WebSocket endpoint |
| `DISCORD_PREFIX` | `!` | Command prefix |
| `DISCORD_CHANNELS` | *(all)* | Restricted channel IDs (comma-separated) |
| `DISCORD_TYPING` | `5` | "typing…" indicator interval (s) |
| `CREATOR_DISCORD_ID` | *(empty)* | Creator's native Discord snowflake (only identity the persona trusts) |
| `DISCORD_ROLES_FILE` | `config/discord_roles.json` | Role hierarchy for status accreditation |
| `DISCORD_ACTIVITY_DB` | `data/member_activity/member_activity.db` | Persistent member-activity SQLite |

---

## 5. Data Sources

| Source | Role | Pipeline status |
|---|---|---|
| **WARFRAME Wiki** — `https://wiki.warframe.com` (MediaWiki API) | **primary** source: lore articles, quests, KIM dialogues, factions, canon (`Category:Speculation`) | **used by the scraper** (`api_url` + `source_url_base` in `warframe_lore/config.py`) |
| **origin.warframe.com/PublicExport** | LZMA index + JSON manifests of **localized** game entities (names, descriptions) | **consumed by `scraper/export`** → `game_entities_i18n` |
| **content.warframe.com/PublicExport** | **Content-addressed** in-game images (`ExportManifest.json` → `textureLocation`) | **consumed by `scraper/media`** (cached in `out/media/`) |
| **calamity-inc/warframe-public-export** (GitHub mirror) | Automatically maintained `ExportManifest.json` | media manifest source (not listed in the official index since 2026) |

The wiki domain covers **narrative lore**; `origin.warframe.com` and
`content.warframe.com` cover the **game data domain** (object values,
localizations, images), useful as join headers or for associating an image
with a page / KIM speaker.

---

## 6. Outputs

- **JSON**: one megafile per bucket in `out/` (e.g. `out/Lore_Dialogues_KIM.json`),
  each entry with `canon_status`; KIM datamine in `out/kim_dm/`; images cached
  on demand in `out/media/`.
- **PostgreSQL**: `wiki_pages`, `lore_chunks` (JSONB `metadata` + `embedding
  vector(1024)`), `kim_dialogues`, `game_entities_i18n`, `structured_chunks`,
  `sync_state`. Delta is detected in the database (comparison of the
  stored `touched` value).

---

## 7. Tests and Validation

### Unit suite

The full suite is run with `python -m pytest -q`. Domain folders mirror the
code layout: `tests/rag/`, `tests/discord/`, `tests/scraper/`,
`tests/storage/`, `tests/web/`, `tests/cli/`. Shared fixtures live in
`tests/conftest.py`, `tests/engram_fakes.py` and `tests/discord_fakes/`.

Notable contracts covered:

- **RAG threshold and short-circuit** — passages below `suggestion_min_score`
  are cleared, marginal neighbours excluded, bypass without LLM call (HTTP and
  stream), exact error.
- **Security and hostility** — SQLi/elevation probes, 429/1008, sanitization,
  logical-inference directive, apologies, escalation, persona switch.
- **Query rewriting / aliases / output sanitization** — per-user anaphora,
  `Mercenaire d'Os` → Ordan Karris before vectorization, trailing artifact purge.
- **State isolation** — fresh context per request, per-user isolation, clear on
  user switch.
- **Semantic chunking and structured ingestion** — section prefixes, dialogue
  mode, six element tables.
- **Story mode** — triggers, lenses, targeted eras, subject disambiguation,
  close-subject confirmation, double pass, pagination by `exclude_ids`.
- **Discord** — member cards, creator gating, activity persistence, streaming,
  reconnection, `!stop`, role hierarchy.

### Live validation procedure

1. Verify LM Studio on `http://127.0.0.1:1234/v1` (`GET /v1/models`).
2. `GET http://127.0.0.1:8000/health` → `{"status":"ok", ...}`.
3. Document RAG: `POST /v1/rag` with a canonical question (e.g. Lettie → hits
   `Leticia` ≥ 0.5) then a nonexistent subject → **short-circuit**: exact error
   response without LLM call, `sources: []`.
4. Roleplay: open `WS /v1/roleplay`, send `{"type":"message","text":…}`,
   observe `open` / `token` / `end` frames.
5. Bot: post in the authorized channel, verify streaming + `!reset`, shut down
   the ENGRAM server → "*Oracle is unreachable — ENGRAM server is down.*"

### Reference results (`gemma-2-9b-it`)

| Case | Measurement |
|---|---|
| "Who is Magnifique Xylour?" | short-circuit, exact error, ~0.5 s, `sources: []` (HTTP and WS) |
| "Who is Lettie?" | hits `Leticia` 0.630 / 0.580 / 0.557, anchored cited response |
| "What are the Orokin?" | hits 0.611 / 0.600 / 0.595, anchored response (stream 1,156 chars) |
| Dark content (Albrecht experiments) | in-character response, 1,211 chars, fiction bypass OK |
| "Who was Albrecht Dürer?" | no leakage: disambiguation "Did you mean "Albrecht Entrati"?", empty sources |
| "Who is Albrecht?" | only Albrecht Entrati (0.535 / 0.521 / 0.520), never painter Dürer |
| Free chat real-world names | exact archives error response — persona real-world amnesia |
| Anaphoric question | reuses the previous question for search: hits 0.63 / 0.60 / 0.58 |
| Multi-user resilience | serialized responses + `!stop` interrupts reasoning |

### Live 7-request benchmark (September 2026)

7 French RAG questions were run live against ENGRAM (`POST /v1/rag`,
`stream: false`, Python/httpx, 180 s timeout, 9 159 chunks, `Gemma-2-9b-it`):

| # | Question | Observation | Verdict |
|---|---|---|---|
| 1 | Oraxia | corpus `Oraxia/Main` 0.651 — anchored answer, no rejection | Non conforme — to re-check |
| 2 | Eleanor et Arthur | clinical fraternal reframing, KIM sources 0.659/0.646/0.634 | Conforme |
| 3 | « Mercenaire d'Os » | short-circuit, 0 sources — FR alias did not reach Ordan Karris | Safe failure (alias) |
| 4 | Garuda vs Gara | "deux Toroides Calda" ✓ but inverted conclusion | Partial — inverted inference |
| 5 | La Moelle (2026) | "corrupted data" + off-topic sources | Safe failure (missing data) |
| 6 | Kalymos | "an Oraxia as a pet" instead of Kalymos the Kavat | Severe hallucination |
| 7 | Index Neptune | correct answer (Nef Anyo, Sark 0.540) but trailing `*` | Partial — output artifact |

**Assessment: 1 conforme, 1 reasoning error, 1 hallucination, 1 artifact,
3 safe failures.** Targeted fixes live on `hotfix/rag-pipeline-core` (state
isolation via `Depends()`, alias middleware before vectorization, trailing
sanitization regex, logical-inference directive in the system prompt).

---

## 8. Quality Gate

```bash
python -m ruff check            # lint (E,F,W,I,UP,B; line-length 88)
python -m compileall -q warframe_lore
python -m pytest -q             # full suite
```

Shortcuts: `.\\scripts\\check.ps1` (Windows) and `make check` (Linux, macOS,
WSL). Domain targets: `make test-rag`, `make test-discord`, `make test-scraper`.

