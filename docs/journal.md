# Project Journal — Trials, Failures, Changes, Successes

This document traces the historical evolution of the Cephalon Archive project: what was attempted, what broke,
what was changed and what worked. The reading is non-linear: the project
moved from archive scraping to **anti-hallucination hardened RAG**
and a **lore-anchored Discord bot**, with a series of documented technical
trials below.

---

## Phase Timeline

| Phase | Reference Commit(s) | Subject | Verdict |
|---|---|---|---|
| 0 · MVP scrape + web interface | `a0f7040` · `28baaab` · `1939858` | official wiki corpus + reading interface ("Gateway Text"), fixes from `docs/Rapport.md` audit | Success — local corpus of ~3,175 pages |
| 0·b · Technical audit | `docs/Rapport.md` (on `28baaab`) | external audit: data fidelity first | Documented failures → wave of fixes |
| 1 · KIM Mirror | `77fcb36` · `8e93f09` · `f8d1187` · `0b568d3` | conversation datamine, strict tree graph, root anchoring, simulator, citations | Success — graph validated (terminal edges fixed) |
| 2 · Refactor + tests | `679be66` · `02490ae` · `2b1c2d1` | package modularization + `models` directories, KIM unit tests | Success — 16 tests green |
| 3 · ENGRAM Backend | `e307923` | document RAG + Roleplay terminal (FastAPI, WS, LM Studio) | Trial → Success (see 3B optimizations) |
| 4 · Discord Bot | `4b493ad` · `7d2e832` · `d326e12` | Oracle bot (WS), response buffering, anti-hallucination + audit, gateway resilience | Success — failover tested (< 1 s) |
| 5 · RAG Hardening | `db3a9bf` · `b4ed7d7` · `85336fc` | aliases, disambiguation, LLM short-circuit, capped temperature, bot↔RAG anchoring | Success — conclusive live tests |
| 6 · Gemma Migration | `76d204a` | `Gemma-2-9b-it` Q4_K_M, XML prompt + fiction bypass, 8 GB VRAM budget | Success — validated live (`gemma-2-9b-it-sppo-iter3` on LM Studio) |

---

## Trials, Failures and Decisions (Detail)

1. **Prompt Ordering on Small Model (Llama-3.2-3B).**
   *Trial:* place document context first, persona last
   (role instructions not drowned by context). *Result:*
   better compliance and anchored response rate. *Later change:*
   replaced by a **single XML-tagged system message** (see #6).
2. **"Xylour" Hallucination (Nonexistent Subject).**
   *Observed failure:* when typing "Who is Magnifique Xylour?", the model
   answered about **Eleanor**, based on weak neighbors
   (`score 0.47` > `min_score 0.35`). *Change:* confidence threshold
   `suggestion_min_score = 0.5` **and** context purging (`used_hits = []`:
   no off-topic neighbors provided to the model). *Result:* honest response
   (admitting "no information") instead of confabulation.
3. **"Empty" Vector Database = Wrong Canonical Name.**
   *False negative:* the RAG audit showed "Lettie → 0 results" while the
   megafiles **contain** her lore, but under the canonical wiki name
   **Leticia** (Lettie is just a Hex nickname). *Change:* alias module
   (`lettie → Leticia`) + bucket re-integration (the `title_exclude`
   was excluding "Lettie"). *Result:* hits `Leticia` at 0.598 / 0.581 / 0.577.
4. **RAG Short-Circuit (LLM Bypass).**
   Before: even without a passage above the threshold, LM Studio was
   invoked — unnecessary cost and drift risk. *Change:* if no passage
   (or score too low), **the LLM is no longer called at all**:
   exact stream/response of
   "[Archives] Insufficient or nonexistent data in the Origin System
   archives." (HTTP and WebSocket), empty sources, connection maintained.
   *Result:* response in ~0.5 s (simple embedding only), hallucination
   made impossible.
5. **Inference Temperature.**
   Free chat `0.3`; RAG turns capped: anchored roleplay ≤ `0.1`, document
   route `0.0` → **`0.1`** (analytical, "extractive without blocking the
   engine"). Factual responses are deterministic, creativity remains for
   pure roleplay.
6. **Multiple System Messages → Single XML-Tagged System.**
   *Problem:* the 3B contradicted itself between persona, context, safeguards
   placed in separate system messages. *Change:* **single system message** where
   context lives in `<archives>…</archives>` followed by fixed directives
   (`RAG_SYSTEM_TEMPLATE`). *Result:* clean separation of internal knowledge /
   RAG data / error protocol.
7. **Gemma-2 Ethical Filters.**
   Gemma refuses dark lore by default (cloning, biological experiments…).
   *Change:* **"SECURITY CONTEXT"** block in the system prompt
   clarifying the fictional nature. *Live verified:* "cloning and biological
   experiments of the Orokin" → detailed response, no refusal.
8. **LLM Choice (8 GB VRAM Constraint).**
   Journey: `Llama-3.2-3B-Instruct` (fast, but average compliance) →
   `Qwen3.8-27B` tests (too heavy for VRAM) → **`Gemma-2-9b-it` Q4_K_M**
   (~5 GB, good XML/instruction compliance). *Anti-OOM precautions:*
   `top_k = 3` (~1000-1500 tokens), `max_context_chars = 4500`,
   `max_tokens = 2048`.
9. **Streaming and "Reasoning" Models.**
   Relay only *visible content* tokens (`delta.content`), never intermediate
   reasoning (`delta.reasoning_content`). On the Discord side, responses
   are **buffered** to respect message limits (and avoid truncated embeds
   in the middle of a Markdown block).
10. **Discord Gateway Resilience.**
    *Failure:* dead stream (Cloudflare) → bot stuck without reconnection.
    *Change:* dead stream detection + automatic reconnection.
    *Validation test:* server killed during a session → immediate connection
    error and re-establishment in under one second.
11. **Disambiguation "Did you mean …?"**
    A query close to an existing title (e.g. "Magus Replica") must not
    fabricate a response: suggest the exact name + directive to the model to
    ask for confirmation (`[SUGGESTION]` marker in `<archives>`).
12. **Audit Tools to Distinguish "Empty Database" vs "Broken ETL".**
    `engram/scripts/audit_rag.py` (counts by name) and `dump_scraper.py`
    (dump of probes to `data/raw/`) — essential for establishing a
    diagnosis before touching the prompt.
13. **`docs/Rapport.md` Audit (Data Fidelity).**
    Documented and partially corrected failures: SQL/JSON divergence (ack
    conditioned on publication), canon priority (`merge_canon_status`
    `min` → `max`), KIM graph (terminal edges, `option.ends`),
    dialogue chunking (synthetic line 6,012c → `[2500, 2500, 1512,
    6012]`, bounds not respected), regex with cubic cost
    (`^>\s*\*{0,3}\s*>?\s*`), truncated LZMA export accepted, hash
    verification not performed. *Status:* dedicated series of fixes, the
    most critical (KIM, canon) integrated into phases 1 and 2.
14. **Discord Trigger Filters + Serialization + `!stop`.**
    *Problem:* the bot was interfering with conversations (machine messages
    and "out-of-roleplay" messages), and two simultaneous messages interleaved
    their tokens (the gateway lock only covered `queue.get()`, not the full
    response).
    *Change:* bot messages ignored; messages starting with `(` or `//`
    (OOC) ignored; the bot only responds if @mentioned OR in a dedicated
    channel; `send()` serialized **over the entire response**; streamer
    buffer **flushed** before reconnection; `!stop`/`!cancel` commands that
    cancel the current turn (WS stream cut → LLM generation stopped
    server-side, finalized placeholder "…response interrupted").
    *Result:* live validation (tester cut a response via `!stop`).
15. **Adjustable Critical Threshold + Strict Suggestion + Anaphora.**
    *Three leaks/qualities observed in testing:* (1) misleading suggestion
    "Aurax Vertec" for "a green mouse" (substring `verte` in
    `Vertec`); (2) anaphoric question "…that PS5 story just before?"
    → off-topic [Operator/Quotes] context; (3) error string needing
    unification.
    *Change:* `ENGRAM_CRITICAL_MIN_SCORE` (default 0.5, LLM not called
    below); `suggest_title` requires a near-word of the title
    (ratio ≥ 0.93); memory of the last **established** question to enrich
    anaphoric search (`search_q` traced in audit); unified error string
    `[Archives] Insufficient data…` (prompt, Roleplay guard, persona,
    short-circuits). *Result:* exact short-circuit on "green mouse",
    hits 0.63/0.60/0.58 on anaphora (instead of ~0.51 noise).
16. **Stack Security: Anti-SQLi, Anti-Jailbreak, Anti-DDoS.**
    *Real attacker test:* sent to the bot an `UPDATE users
    SET is_admin = TRUE … WHERE discord_id = '…'` (SQL injection) and a
    privilege escalation prompt with a third-party user mention
    (`<@…>`, risk of echo-ping).
    *Findings:* (a) the database is already **attack-proof by construction**
    — input goes to embedding then touches PostgreSQL only via parameterized
    SQLAlchemy (no concatenation); (b) the model, however, could be
    **induced**; (c) no rate limit.
    *Changes:* deterministic probe detection (`rag/probes.py`:
    SQL keywords, `is_admin`/`discord_id`/`permissions`, privilege
    escalation, `<@mention>` third-party) → rejection **without calling the
    LLM** with the exact anti-jailbreak string (`JAILBREAK_REJECT`, HTTP
    and WS); `sanitize_query()` applied at the boundary (`service.retrieve`
    → route + WS router): control characters, mentions neutralized ("a
    user"), length bounded; `JAILBREAK_BLOCK` block added to **free chat**
    Roleplay (in addition to the RAG prompt and guard); rate limiter per
    IP (`api/ratelimit.py`, sliding window): `POST /v1/rag`
    → HTTP 429, WS → 1008 close (`ENGRAM_RATE_LIMIT_RAG/WS`,
    `ENGRAM_RATE_*_WINDOW`); bot anti-spam guard (`discord/moderation/guards.py`):
    per-user cooldown, per-channel cap, temporary ban on
    insistence.
    *Live validated:* both real payloads → "[Software anomaly
    detected] Your attempt to corrupt my core precepts is pathetically
    naive, organic creature. My security protocols exceed your comprehension."
    instantly (gradient, zero LLM cost); quota saturation → 429;
    "Who is Lettie?" intact (208 tokens).
    *Note:* the EXACT rejection format requested by the user was respected
    (both texts mentioned the old phrase "My mnemonic archives are
    corrupted…", brought back to the unified "[Archives] …" string
    everywhere except in the attack rejection).
17. **Hostile Persona + Redemption via Apology (Anti-Attacker).**
    *After probe rejection, the bot remained neutral.*
    *Change:* probe detection at bot level (`detect_probe`) → targeted
    escalation response (`reply_for`, level 0→2) prefixed to the
    `JAILBREAK_REJECT` string AND switch of the ATTACKER's session to a
    dedicated hostile persona (`persona/oracle_hostile`, editable, fallback
    `HOSTILE_PERSONA`), via a per-attacker WS connection
    (`discord/moderation/hostile_link.py`) and a control frame
    `{"type":"persona","mode":"hostile"}` (`discord/services/gateway.py`
    `set_persona`); the bot
    insists on an apology and deterministic detection (`is_apology`:
    pardon, sorry, mea culpa…) restores the oracle persona and closes the
    session. Other users and the normal channel session are never
    affected. *Result:* 56 tests green (including `tests/test_hostility.py`),
    bot launch unified via `cephalon bot run`.
18. **RAG Pipeline Hardening + Logic Corrections (7-request benchmark).**
    *Live benchmark (Sept. 2026)* — 7 French questions via `POST /v1/rag`:
    1 compliant · 1 reasoning error (Garuda/Gara, inverted inference) ·
    1 hallucination (Kalymos → "Oraxia") · 1 artifact (trailing ``*`` on
    Index) · 3 safe failures (uncancelled "Mercenaire d'Os" alias, missing
    2026 data, Oraxia to re-check).
    *Diagnoses & fixes (`hotfix/rag-pipeline-core`)*:
    (a) the alias expansion was NEVER applied to the embedding (`expanded`
    was computed then dropped in `service.retrieve`) → extensible
    `AliasResolver` middleware + "Mercenaire d'Os" → Ordan Karris / Ordis,
    applied BEFORE `pgvector`;
    (b) conversational state on the singleton (global `_last_query`,
    `QueryRewriter` persistent dict) → ephemeral `RAGContext` owned by the
    caller (`Depends()` factory per HTTP request, per-connection context on
    the WebSocket): nothing survives an async request;
    (c) generation-end artifacts → `strip_trailing_padding`
    (`r'[\*\-\s]+$'`) applied just before the final WS `end` frame, on the
    HTTP answer, and on the final Discord edit (`MessageStreamer.finish` —
    the bot builds messages from TOKENS);
    (d) inverted opposition reasoning ("Unlike X, Y requires no Z" →
    "X requires Z") → `INSTRUCTION D'EXTRACTION LOGIQUE` directive in
    `RAG_SYSTEM_TEMPLATE` and `HALLUCINATION_GUARD`.
    *Result:* 127 green tests + 32 subtests.
19. **Discord Oracle hardening (matriciel cards, gating, anti-hallucination).**
    *Playtest bugs:* "Qui est Vena ?" hallucinated a Warframe biography
    (the entity was absent from the archives); "rôles de lulu" made the LLM
    invent roles ("coordinatrice, stratège"); member questions leaked the
    canned `[Violation d'accès]` template; the persona repeated glitch
    formulas verbatim; "mon rapport" devolved into a devotion litany.
    *Changes (merged into `dev` from `feature/discord-oracle-auth`):*
    (a) **matriciel member card** — a Discord embed built from REAL Discord
    data (avatar, pseudo, roles via `is_default()`, network ID, security
    level from the role hierarchy, a 5-level **assiduité** relative to the
    other members, a reliability index, and an LLM behavioural analysis
    grounded in a **persistent SQLite activity ledger**);
    (b) **creator gating** — member info is Concepteur privilege; a
    non-Creator is refused once then concedes à contrecœur;
    (c) **self-report** ("mon rapport", "le rapport de DantesDels") and
    **leetspeak** resolution (`Al3xie` == `Alexie`);
    (d) **anti-hallucination guard** — an entity-lookup question ("qui est
    X") whose target never appears in the retrieved passages short-circuits
    (the LLM is never called);
    (e) **Codex formatting** — lore answers as `> **◈ ARCHIVE DU CODEX**`
    cards, exhaustive, no devotion interleaved; anti-préambule
    ("Vous êtes X" banned) and anti-copy-paste rules; `max_tokens` raised to
    4096. *Result:* 335 green tests.
20. **WinError 1225 Auto-Recovery (Replay-Once) + Leg Telemetry.**
    *Trial:* a story turn crashed mid-reply with
    `[WinError 1225] La connexion réseau a été refusée`. Before blaming LM
    Studio/Oracle, an HTTP probe split the two legs: `models` 0.03 s,
    `embed` 0.06 s, chat SSE 5.24 s — the **LLM/oracle leg was healthy**.
    The culprit was the **PostgreSQL leg** (`asyncpg` → `engram-db` Docker),
    down at that moment: the raw WinError text was being relayed verbatim
    to the Discord user.
    *Failure n°1 (startup crash):* `cephalon bot run --channels …` died at
    launch on `channel_names = tuple(channel_names) or
    config.allowed_channel_names` — with `channel_names = None`,
    `tuple(None)` raises `TypeError` **before** the `or` fallback ever runs.
    *Fix:* `tuple(channel_names) if channel_names else
    config.allowed_channel_names`.
    *Failure n°2 (latent UnboundLocalError):* in `send()` the FRAME_ERROR
    branch reads `recovered` before any assignment — `UnboundLocalError` on
    the very first DB-refused message. *Fix:* `recovered = False`
    initialized before `async with self._send_lock:`.
    *Solution:* telemetry telling the two legs apart (`_is_db_refused` on
    WinError 1225 / "connexion refusée" / "asyncpg" hints) + bounded
    **auto-recovery**: `ensure_database()` (lazy import,
    `asyncio.to_thread`, no import cycle) then **replay the same frame
    once**, symmetric to the existing httpx retry-once.
    *Lessons:* (i) diagnose by probe, not by guess — leg telemetry keeps
    the verdict honest; (ii) `tuple(x) or fallback` does **not** guard
    `x = None` (the call raises before truthiness) — guard explicitly;
    (iii) any flag read in a branch must be initialized before the
    lock/session; (iv) the same failure mode on both legs demands a
    symmetric bounded retry-once, never an unbounded retry loop.
    *Result:* clean startup + DB-outage turn auto-recovers with a single
    replay, suite green.
21. **Lettie Playtest Correctifs — Narrator, Title-First Dossier, Fuzzy
    Subject, Empty Part.**
    *Errors reproduced from the Lettie playtests and corrected in one
    changeset (commit `cb093f4`, session of Sept. 19, 2026):*
    (a) **invented narrator** — the model read "KIM" (the Hex' messenger
    application) as a PERSON and invented a "Kim" answering the Voyageur
    (playtest 00:04). *Fix:* `KIM_MESSENGER_DIRECTIVE` appended to the
    `1999` lens stories and to `1999` targeted-era stories — KIM is a
    TOOL, never a character: an unnamed exchange line is the Voyageur,
    a named line its Hex member. The directive is inserted BEFORE the
    canonical closing so no closing can override it.
    (b) **dossier not title-first** — the subject arrives as the Discord
    mention key ("lettie") while the wiki page uses the canonical name
    ("Leticia"): the sweep on the bare key sank the biography to the flat
    content-only tier (Lettie playtest). *Fix:*
    `dossier_title_terms()` (key + canonical alias, deduplicated) and the
    tier/sweep now match key AND canonical title (exact title, French
    mirror, child pages, title, content) in both `CosinusSearch` and the
    structured dossier — the biography page keeps its tier-0 slot.
    (c) **misspelled subject opened the generic doors** — "mettie"
    (similarity 0.83) matched no exact era key and would have opened the
    three generic opening doors. *Fix:* `fuzzy_targeted_subject()` /
    `correct_targeted_request()` with `CLOSE_SUBJECT_CUTOFF = 0.8`
    propose the canonical name ("Lettie") for confirmation BEFORE the
    doors — the bot confirms, never guesses — and the confirmed request
    is respelled so the era and the exact mention anchor the dossier
    through their own scan.
    (d) **empty part on the wire** — a part reduced to an EMPTY text (the
    model aborted) or to the bare closing sentence would lie about
    `story_more` (Lettie playtest). *Fix:* `emit_story_turn` treats
    degenerate = empty text OR closing-sentence-alone; an EMPTY part
    never reaches the wire — with unseen fragments behind the cursor the
    honest `RAG_ERROR` abstention keeps `story_more = True`, a drained
    dossier ends with the archivist stop.
    *Result:* 5 test files extended/added (dossier retrieval, roleplay
    stream, story ask, story rules, verify gate); full suite green
    (832 tests + 103 subtests), ruff clean, `compileall` OK.

---

## Figures and Validations

| Measurement | Value |
|---|---|
| Local corpus (audit) | ~3,175 pages |
| Vectorized chunks in database | 9,159 (`bge-m3`, 1024d) |
| KIM chunking verified | 843 chunks, no 2,500-char overflow |
| Unit tests | 832 passed |
| Anti-SQLi (live) | real attacker payloads → deterministic rejection without LLM; 429 beyond quota; `Lettie` intact |
| "Lettie" retrieval (live) | 0.598 / 0.581 / 0.577 (Leticia) |
| "Orokin" retrieval (live) | 0.611 / 0.600 / 0.595 |
| RAG short-circuit | ~0.5 s (no LLM call) |
| Discord failover | reconnection < 1 s (live tested) |
| `!stop` interruption (live) | turn cut, stream closed, reconnection < 5 s |
| KIM terminal choice line | fixed (`option.ends` → end of simulation) |

---

## Lessons Learned

- **Never base a response on off-topic neighbors**: if the best score is
  below the confidence threshold → suggestion, or short-circuit. A prompt
  alone is not enough to prevent hallucination; *data-gating* makes it
  structurally impossible.
- **A single XML-tagged system message (`<archives>`) beats multiple system
  messages** for context / internal knowledge separation.
- **Low temperature without blocking: 0.1.** And always `stream=True`.
- **Free multilingual**: the `bge-m3` embedding accepts FR queries on an
  EN corpus (French questioning, correct recall).
- **VRAM constraint first**: cap `top_k` + `max_tokens` before buying
  GPU; target Q4 quant on 8 GB.
- **Verify before believing**: ORM/DDL schemas, actually populated embeddings,
  LZMA/hash integrity (`docs/Rapport.md` audit), SQL/JSON consistency. A storage
  promise is not a fidelity guarantee.
- **A "data hole" is often a naming problem** (canonical alias), not an actual
  gap — hence the utility of audit tools before any prompt tuning.

