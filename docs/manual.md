# User Manual — Cephalon Archive

> Day-to-day usage of the three interfaces: the local web UI, the Discord bot
> and the ENGRAM API. Architecture and specifications live in
> [`architecture.md`](architecture.md) and [`specifications.md`](specifications.md).

---

## 1. Local Web Interface (`cephalon ui`)

`pip install -e .` installs the `cephalon-ui` command, which launches a mini
local HTTP server (stdlib, no browser-side dependency) exposing a modern dark
interface for browsing the retrieved lore:

- **Overview** — global statistics + bucket cards;
- **Bucket Browser** — all pages with their `canon_status`;
- **KIM Dialogues** — conversations structured by speaker (`> **Name:**`);
- **Recent** — latest inserted / updated pages;
- **Full-text Search** — across all content (`/api/search`);
- **Media** — portraits / objects via the Public Export index (`/api/media`);
- **Inspector** — RAG debug view (retrieval, scores, prompt, guards);
- **Timeline** — curated lore chronology (depth-by-depth graph).

Data is read directly from megafiles `out/*.json` (read-only, no network access;
the network is used only for on-demand images). Responses are `gzip`-enabled
to serve large dialogues without overwhelming the browser.

```bash
cephalon ui                       # launches server + opens browser
cephalon ui --port 8123           # fixed port
cephalon ui --no-browser          # without auto-open
cephalon ui --out ./out           # different megafiles folder
```

### Standalone executable

```bash
pip install pyinstaller
pyinstaller --onefile --name cephalon-ui \
  --add-data "warframe_lore/web/static;warframe_lore/web/static" \
  --paths . packaging/launch_ui.py
```

The result (`dist/cephalon-ui.exe`) reads the `out/` folder from the current
directory, then any folder passed via `--out`. Rebuild after adding buckets
(content is reread on each request, no embedded index).

---

## 2. "Loremaster Oracle" Discord Bot

Launch with `python -m warframe_lore.discord.main --channels <id>` (or
`cephalon bot run`). The bot responds in authorized channels (option
`--channels` / `DISCORD_CHANNELS`), or if @mentioned elsewhere. Messages
starting with `(` or `//` (and bot messages) are ignored ("out-of-roleplay").

### Behaviour

- **Lore questions** trigger RAG (lexical triggers: *who, when, what, where,
  why, how many, orokin, tenno, warframe, void, kuva, hex, fragments, chimer,
  treasures, reign…*) and stream the answer through progressive message edits.
  Non-lore questions go into free discussion. Responses are **serialized**:
  concurrent users wait their turn, and the streaming buffer is flushed between
  turns.
- **Matriciel member cards** — "qui est X ?", "rapport matriciel de X",
  "rôles de X", "ses rôles", "mon rapport" (self-report) resolve a real Discord
  member (exact, prefix, or leetspeak: `Al3xie` == `Alexie`) and answer with an
  embed: `RAPPORT MATRICIEL`, pseudo + network ID, real Discord roles, security
  level (role hierarchy), 5-level **assiduité** relative to other members, a
  reliability index, and an LLM behavioural analysis grounded in recorded
  interactions. Activity is persisted in
  `data/member_activity/member_activity.db` (SQLite, survives restarts).
- **Creator gating** — the Concepteur always gets a member card; a non-Creator
  is **refused once** ("Requête refusée, organique… insistez si vous l'osez.")
  then **concedes à contrecœur** if they insist on the same member. A
  non-Creator citing the Concepteur's pseudonym triggers the persona's
  possessive jealousy instead.
- **Commands**: `!ping` — "Oracle ready."; `!reset` — new session; `!stop`
  (or `!cancel`) — interrupts the current response (reasoning stopped
  server-side, message finalized "…response interrupted"); `!help` — help.
- **Narrative tales** — a story request ("raconte-moi l'histoire de X",
  "l'histoire de…") opens a **targeted lore dossier** (the subject's own pages
  first — biography, sections, title matches — with aliases resolved, e.g.
  `lettie` → `Leticia`) and is told in French through a **double pass**
  (invisible factual draft at 0.1, then the narration). An ambiguous request
  opens the **lens doors** (initiate / cosmogonic / 1999); a misspelled subject
  ("mettie") is **confirmed** before the doors ("Voulais-tu dire « Lettie » ?"),
  never guessed. Each part ends with the mandated closing (invitation while
  fragments remain, archivist stop once drained); empty parts are never served.

### Failure modes (by design)

- Subject absent from archives → *"[Archives] Insufficient or nonexistent data
  in the Origin System archives."* (no fabrication, the LLM is not called).
- Low ambiguity → *"Did you mean "{suggestion}"?"* (strict suggestion).
- Anaphoric question ("that story… just before?") → search reuses the last
  established subject, not tag noise.
- ENGRAM server down → *"Oracle is unreachable — ENGRAM server is down."*;
  automatic reconnection if the stream died.

---

## 3. ENGRAM API

- `POST /v1/rag` — body `{"question": "…", "stream": false}` →
  `{"answer", "sources": [{"page_title", "content", "score"}]}`; with
  `stream: true`, the response switches to `text/plain` (token stream).
- `WS /v1/roleplay` — received frames: `{type: "open"}`,
  `{type: "token", token}`, `{type: "end", text}`; sent frames:
  `{type: "message", text, rag?}`.
- `GET /health` — liveness probe (`{"status": "ok"}`).
- `GET /docs` — Swagger.

```bash
# Start PostgreSQL + pgvector (docker-compose at root)
docker compose up -d

# Apply schema (warframe_lore/storage/db/init_db.sql) — once
psql -U warframe -d warframe_lore -f warframe_lore/storage/db/init_db.sql

# Populate + vectorize chunks
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

# Start the ENGRAM API
uvicorn warframe_lore.engram.api.main:app --port 8000
```

See [`warframe_lore/engram/README.md`](../warframe_lore/engram/README.md) and
[`warframe_lore/engram/rag/README.md`](../warframe_lore/engram/rag/README.md)
for the execution trace and thresholds.

---

## 4. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Systematic short-circuit response | Empty corpus or thresholds too high → `cephalon status`, then check neighbour scores (RAG audit / inspector). |
| `404 model not found` | The model requested by `ENGRAM_CHAT_MODEL` is not loaded in LM Studio → load `gemma-2-9b-it` (Q4_K_M). |
| VRAM OOM | Lower `ENGRAM_MAX_TOKENS` / `ENGRAM_TOP_K`, or switch to `llama-3.2-3b-instruct`. |
| Empty database / missing schema | `cephalon init-db` then `cephalon run`. |
| Silent bot | Check `DISCORD_TOKEN`, channel restriction, and that ENGRAM `:8000` listens (`netstat -ano | findstr 8000`). |
| Persona not updated | Edit `persona/oracle`; it is read at session launch. |

For the developer quality gate, see the root README ("Quality Gate").
