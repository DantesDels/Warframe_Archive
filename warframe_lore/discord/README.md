# Discord Bot — Oracle Terminal (Roleplay via ENGRAM)

A `discord.py` bot that connects a Discord server to ENGRAM's **WebSocket
Roleplay terminal** (`/v1/roleplay`): each accepted message is forwarded to
Oracle, tokens are broadcast live (progressive message edits), and each channel
keeps its own session (conversational memory via the server's sliding window).

## Prerequisites

- ENGRAM API running: `uvicorn warframe_lore.engram.api.main:app --port 8000`
  (auto-started by `cephalon bot run` when it does not answer yet).
- LM Studio up (port 1234) with the chat and embedding models loaded.
- `discord.py>=2.0`: `pip install "discord.py>=2.0"` (or `pip install -e ".[discord]"`).

## 1. Create the Bot on the Discord Portal

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token (secret).
   * Check `Message Content Intent` and `Server Members Intent` — the first is
     required to read messages, the second to accredit the speaker's roles.
   * (Optional) disable `Public Bot` for private use.
3. **OAuth2 → URL Generator** tab:
   * scope `bot`; permissions `Send Messages`, `Read Message History`,
     `View Channels`, `Manage Messages` (edits), `Embed Links` (matriciel cards),
     `Attach Files` (wiki portraits), `Add Reactions` (👍 / 👎 verdicts).
   * Open the generated **invitation URL** to add the bot to the server.

## 2. Configuration

Overrides via environment variables, a `.env` file at the project root (read
automatically, no dependency), or CLI arguments:

| Parameter | Env | CLI | Default |
|---|---|---|---|
| Token | `DISCORD_TOKEN` | `--token` | — (required) |
| WS URL ENGRAM | `ENGRAM_WS_URL` | `--ws` | `ws://localhost:8000/v1/roleplay` |
| Command prefix | `DISCORD_PREFIX` | `--prefix` | `!` |
| Dedicated channels | `DISCORD_CHANNELS` | `--channels` | — (mention only) |
| `typing` interval | `DISCORD_TYPING` | — | `5` |
| Concepteur snowflake | `CREATOR_DISCORD_ID` | — | — (feature off) |
| Role map | `DISCORD_ROLES_FILE` | — | `config/discord_roles.json` |
| Shared ledger (SQLite) | `DISCORD_ACTIVITY_DB` | — | `data/member_activity/member_activity.db` |
| Wiki portraits | `DISCORD_IMAGES` | — | `1` |
| Media index folder | `WF_OUTPUT_DIR` | — | `out/` |

The Concepteur identity is **native**: the bot compares `message.author.id` with
`CREATOR_DISCORD_ID` and only ever forwards the derived boolean `creator` — the
snowflake never leaves the process.

## 3. Launch

```bash
# 1) project root: create .env (secret, not versioned)
#    DISCORD_TOKEN=MTE...  (bot token from the Discord portal)

# 2) from the project root (ENGRAM started automatically if needed)
cephalon bot run
# (equivalent: python -m warframe_lore.discord.main, or the "loremaster" script)

# dedicated channel + verbose logs:
cephalon bot run --channels <ID> --verbose
```

## 4. Commands

All commands start with the configured prefix; `!help` (or `!aide`) lists them.

| Command | Effect | Privilege |
|---|---|---|
| `!reset` | Wipes the speaker's short-term memory server-side, closes the channel session | everyone |
| `!ping` | Terminal liveness (no ENGRAM round-trip) | everyone |
| `!stop` / `!cancel` | Interrupts the running reply: the WS stream is cut, so the generation stops too | everyone |
| `!stats` | Runtime counters: turns by kind, RAG share, refusals, errors, p50 latency, 👍/👎 tally | everyone |
| `!fiche [pseudo]` | Matriciel card of a member (own card without argument) | Creator privilege (see §6) |
| `!channel on\|off` | The bot answers (or stays silent) on this channel | Creator / Haut Commandement |
| `!lang fr\|en` | Language of the answers on this channel | Creator / Haut Commandement |
| `!rag on\|off` | Ground the answers on the lore archives | Creator / Haut Commandement |
| `!images on\|off` | Attach the official wiki portraits | Creator / Haut Commandement |
| `!persona oracle\|hostile` | Persona of this channel | Creator / Haut Commandement |

Channel settings are **persisted** in the shared SQLite ledger (`!channel off`
never locks the channel: commands still work while the Oracle is muted).

## 5. Security and Hostility (Anti-Attacker)

- **Deterministic detection** (`engram/rag/probes.py`): SQL injection, privilege
  escalation (`is_admin`, `permissions`…), third-party mentions `<@id>` →
  rejection **without calling the LLM** with the exact string `JAILBREAK_REJECT`
  (HTTP `POST /v1/rag` **and** WS `/v1/roleplay`).
- **Rate limit**: sliding window per IP (HTTP 429 / WS 1008 closure) + bot-side
  anti-spam guard (`moderation/guards.py`: user cooldown, per-channel cap,
  temporary block on insistence).  `!stop` bypasses the guard on purpose — it is
  needed exactly while a turn is running.
- **Hostile persona per attacker**: on a probe (`mixins/moderation/hostile.py`)
  the session of **that user** switches to the anti-aggression persona
  `persona/oracle_hostile` via the frame `{"type":"persona","mode":"hostile"}`.
  Other users and the normal channel session are unaffected; the table is
  bounded (`MAX_HOSTILE_SESSIONS`).
- **Répartie**: a direct insult from a non-Creator gets a cold, escalating
  comeback (`moderation/insults.py` + `comebacks.py`); past the threshold the
  attacker's session flips hostile.  The Concepteur's own insults are never
  intercepted — they fall through to the free chat.
- **Redemption via apology**: deterministic detection `is_sincere_apology`
  (`moderation/hostile_link/apology.py`) restores the oracle persona, delivers
  the reply, then closes the hostile session.
- **Persistent strikes**: probe and insolence counters live in SQLite
  (`StrikeLedger`), so a restart does not amnesty an attacker — and they feed the
  reliability index of the matriciel card.

## 6. Matriciel Member Cards

Member information is answered with a Discord **embed** built from **real
Discord data** (never the hallucinating LLM):

```
RAPPORT MATRICIEL
IDENTIFIANT : Aze07
Identifiant Réseau : #194814251502796800
Rôles et Accréditations      ← real roles (bullets, @everyone excluded)
Niveau de Sécurité           ← from the role hierarchy (config/discord_roles.json)
Assiduité                    ← 5 levels, relative to the other members
Indice de Fiabilité          ← activity − insolence/probes
Analyse comportementale      ← LLM observation, grounded in recorded activity
```

- **Triggers**: "qui est X ?", "rapport matriciel de X", "rôles de X",
  "ses rôles" (anaphora), "mon rapport" (self-report), `!fiche`.  Names resolve
  exact, by prefix, or **leetspeak** (`Al3xie` == `Alexie`).
- **Creator gating**: the Concepteur (and `!fiche` from him) always gets the
  card; a non-Creator is **refused once** then **concedes à contrecœur** if he
  insists on the same member.  A non-Creator citing the Concepteur's pseudo
  triggers the persona **jealousy** instead.
- **Persistence**: member activity (message count + recent texts), strikes,
  verdicts and channel settings share ONE batched SQLite ledger
  (`DISCORD_ACTIVITY_DB`), so the indices survive restarts.  `:memory:`
  disables persistence (tests).
- **Wiki portraits**: when `images` is on for the channel, the answer gets the
  official Public Export portrait of the first entity it names (same media index
  as the web UI, downloaded on demand, best effort).
- **Feedback**: every streamed answer is opened to 👍 / 👎; verdicts are
  persisted and summarised by `!stats`.

## 7. Verify

- A message on a dedicated channel (or mentioning the bot) → Oracle replies
  live, the message is edited token by token, then offers the two verdicts.
- `!stats` shows the turns handled since startup; `!reset` starts a fresh
  session; `!stop` cuts a long reply.
- Tests: `python -m pytest tests -q` (the bot pipeline is exercised through its
  real `on_message` with the fakes in `tests/discord_fakes/`, no network).

## Troubleshooting

- **No response**: check that LM Studio answers (`/v1/models`), that ENGRAM runs
  on the expected port, that `ENGRAM_WS_URL` matches, and that the channel is
  dedicated (`DISCORD_CHANNELS`) or the bot was mentioned — and not muted by
  `!channel off`.
- **Slow / empty model**: use a non-reasoning model (Llama-3.2-3B) rather than
  Qwen3 (long reasoning before responding); overridable via `ENGRAM_CHAT_MODEL`
  on the ENGRAM server side.
- **No wiki portrait**: the media index is best effort — check `out/`
  (`WF_OUTPUT_DIR`) and the Public Export cache under `cache/public_export/media`.

## Architecture (SOLID)

Grouped by domain; every package exposes a facade in its `__init__.py`:

| Path | Role |
|---|---|
| `config.py` | `DiscordConfig` (token, WS, prefix, channels, creator ID, roles file, ledger path, images) |
| `bot.py` | `LoreMasterBot` — `discord.Client` composing the mixins; owns `state` + `services`, plus `on_ready`/`close` |
| `main.py` | Console entry point (`launch_bot`, shared with the CLI `cephalon bot run`) |
| `text.py` | Shared text helpers: stopwords, content words, mention tokens |
| `core/` | `state.py` (`BotState` — bounded volatile tables), `sessions.py` (`SessionPool` — gateways, personas, hostile links), `wiring.py` (`BotServices`, `build_services`, `close_services`) |
| `bootstrap/` | `db_bootstrap.py` (PostgreSQL/pgvector auto-start), `engram_bootstrap.py` (uvicorn child + teardown) |
| `mixins/turn/` | `dispatch.py` (`on_message` pipeline + gating), `plan.py` (`TurnContext` → audit label + `MessageFrame`), `routing.py` (RAG/jealousy/member decision), `streaming.py` (placeholder, tokens, reconnect, `!stop`, finishing) |
| `mixins/member/` | `context.py` (accreditation + identity), `roster.py` (name resolution), `snapshot.py` (`MemberSnapshot`), `gate.py` (creator privilege + card) |
| `mixins/moderation/` | `hostile.py` (probes, death sessions, redemption), `insults.py` (répartie), `spam.py` (anti-spam gate), `feedback.py` (👍/👎) |
| `commands/` | `prefix.py` (dispatch table + help), `ops.py`, `card.py`, `channel.py`, `arguments.py` |
| `guild/` | `naming.py`, `questions.py`, `lore.py`, `creator.py`, `roles/` (`RoleHierarchy`, `Accreditation`, dump/scan tools) |
| `moderation/` | Pure defences: `guards.py`, `hostility.py`, `insults.py`, `comebacks.py`, `hostile_link/` |
| `services/` | `transport/gateway/` (`RoleplayGateway` = `connection` + `reader` + `requests` + `controls`), `transport/stream/` (`MessageStreamer`, hard split), `ledger/` (`LedgerDB`, activity, strikes, feedback, stats), `cards/` (snapshot, indices, embed, wiki images), `settings.py` |
