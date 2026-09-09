# Discord Bot — Oracle Terminal (Roleplay via ENGRAM)

A `discord.py` bot that connects a Discord server to ENGRAM's **WebSocket
Roleplay terminal** (`/v1/roleplay`): each message sent on a channel is
forwarded to Oracle, tokens are broadcast live (progressive message edits),
and each channel maintains its own session (conversational memory via the
server's sliding window).

## Prerequisites

- ENGRAM API running: `uvicorn warframe_lore.engram.api.main:app --port 8000`
- LM Studio up (port 1234) with the chat and embedding models loaded.
- `discord.py>=2.0`: `pip install "discord.py>=2.0"` (or `pip install -e ".[discord]"`).

## 1. Create the Bot on the Discord Portal

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token (secret).
   * Check: `Message Content Intent` (Intents) — required to read messages.
   * (Optional) disable `Public Bot` for private use.
3. **OAuth2 → URL Generator** tab:
   * scope: `bot`; permissions: `Send Messages`, `Read Message History`,
     `View Channels`, `Manage Messages` (for edits, or replace with
     `Embed Links`/`Attach Files`).
   * Copy the generated **invitation URL** and open it to add the bot to
     the desired server.

## 2. Configuration

Overrides via environment variables, `.env` file at the project root
(read automatically, no dependency — only if the variable does not already
exist in the shell), or CLI arguments:

| Parameter | Env | CLI | Default |
|---|---|---|---|
| Token | `DISCORD_TOKEN` | `--token` | — (required) |
| WS URL ENGRAM | `ENGRAM_WS_URL` | `--ws` | `ws://localhost:8000/v1/roleplay` |
| Command prefix | `DISCORD_PREFIX` | `--prefix` | `!` |
| `typing` interval | `DISCORD_TYPING` | — | `5` |

Bot commands: `!reset` (new Oracle session on the channel), `!help`.

## 3. Launch

```bash
# 1) project root: create .env (secret, not versioned)
#    DISCORD_TOKEN=MTE...  (bot token from the Discord portal)

# 2) from the project root (ENGRAM running on :8000)
cephalon bot run
# (equivalent: python -m warframe_lore.discord.main, or CLI alias "bot run")

# useful options — dedicated channel + verbose logs:
cephalon bot run --channels <ID> --verbose
# or, if a token must override .env:
$env:DISCORD_TOKEN = "YOUR_TOKEN"    # PowerShell
cephalon bot run
```

Also available via the `loremaster` console script.

## 3. Security and Hostility (Anti-Attacker)

- **Deterministic detection** (`engram/rag/probes.py`): SQL injection,
  privilege escalation (`is_admin`, `permissions`…), third-party mentions
  `<@id>` → rejection **without calling the LLM** with the exact string
  `JAILBREAK_REJECT` (HTTP `POST /v1/rag` **and** WS `/v1/roleplay`).
- **Rate limit**: sliding window per IP (HTTP 429 / WS 1008 closure) +
  bot-side anti-spam guard (`guards.py`: user cooldown, per-channel cap,
  temporary ban on insistence).
- **Hostile persona per attacker**: as soon as a probe is detected
  (`bot.py._handle_probe`), the WS session of **that user** is switched
  to the anti-aggression persona `persona/oracle_hostile` (editable) via the
  frame `{"type":"persona","mode":"hostile"}` (`gateway.set_persona`).
  Other users and the normal channel session are not affected.
- **Redemption via apology**: the bot insists on obtaining an apology
  (`_insist`); deterministic detection `is_apology` (`hostile_link.py`,
  markers: *pardon, excusez-moi, désolé, sorry, mea culpa…*) restores the
  oracle persona and closes the hostile session (`_forgive`).

## 5. Verify

- In Discord, type a message on a channel where the bot is present → Oracle
  responds live (the message is edited token by token).
- `!reset` starts a fresh session (channel history cleared).

## Troubleshooting

- **No response**: check that LM Studio responds (`/v1/models`), that the
  ENGRAM API is running on the correct port, and that the WS URL matches
  (`ENGRAM_WS_URL`).
- **Slow / empty model**: use a non-reasoning model (Llama-3.2-3B) rather
  than Qwen3 (long reasoning before responding); overridable via
  `ENGRAM_CHAT_MODEL` on the ENGRAM server side.

## Architecture (SOLID)

| File | Role |
|---|---|
| `config.py` | `DiscordConfig` (token, WS, prefix, authorized channels) |
| `gateway.py` | `RoleplayGateway` — WS connection per channel, token broadcast, `set_persona` (switch to hostile persona) |
| `streamer.py` | `MessageStreamer` — message editing with buffering (anti-429) |
| `guards.py` | `BurstGuard` — anti-spam (user cooldown, per-channel cap, ban) |
| `hostility.py` | Targeted escalation (`reply_for`, level 0→2) + `HostilityTracker` |
| `hostile_link.py` | Hostile session per attacker (`is_apology`, persona switch/return) |
| `bot.py` | `LoreMasterBot` — `discord.Client`, routing, probe detection (`_handle_probe`/`_insist`/`_forgive`) |
| `main.py` | Console entry point (`launch_bot` shared with CLI `cephalon bot run`) |
