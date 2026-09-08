# Bot Discord — Terminal Oracle (Roleplay via ENGRAM)

Bot `discord.py` qui relie un serveur Discord au **terminal Roleplay WebSocket**
d'ENGRAM (`/v1/roleplay`) : chaque message envoyé sur un canal est transmis à
Oracle, les tokens sont diffusés en direct (edits progressifs du message), et
chaque canal garde sa propre session (mémoire conversationnelle via la
fenêtre glissante du serveur).

## Prérequis

- L'API ENGRAM lancée : `uvicorn warframe_lore.engram.api.main:app --port 8000`
- LM Studio up (port 1234) avec le modèle chat et l'embedding chargés.
- `discord.py>=2.0` : `pip install "discord.py>=2.0"` (ou `pip install -e ".[discord]"`).

## 1. Créer le bot sur le portail Discord

1. Aller sur <https://discord.com/developers/applications> → **New Application**.
2. Onglet **Bot** → **Reset Token** → copier le token (secret).
   * Cocher : `Message Content Intent` (Intents) — requis pour lire les messages.
   * (Optionnel) désactiver `Public Bot` pour un usage privé.
3. Onglet **OAuth2 → URL Generator** :
   * scope : `bot` ; permissions : `Send Messages`, `Read Message History`,
     `View Channels`, `Manage Messages` (pour les edits, ou remplacer par
     `Embed Links`/`Attach Files`).
   * Copier l'**URL d'invitation** générée et l'ouvrir pour ajouter le bot au
     serveur voulu.

## 2. Configuration

Surcharges par variables d'environnement ou arguments CLI :

| Paramètre | Env | CLI | Défaut |
|---|---|---|---|
| Token | `DISCORD_TOKEN` | `--token` | — (requis) |
| URL WS ENGRAM | `ENGRAM_WS_URL` | `--ws` | `ws://localhost:8000/v1/roleplay` |
| Préfixe commandes | `DISCORD_PREFIX` | `--prefix` | `!` |
| Intervalle `typing` | `DISCORD_TYPING` | — | `5` |

Commandes du bot : `!reset` (nouvelle session Oracle sur le canal),
`!help`.

## 3. Lancer

```bash
# depuis la racine du projet (ENGRAM tourne sur :8000)
$env:DISCORD_TOKEN = "VOTRE_TOKEN"         # PowerShell
set DISCORD_TOKEN=VOTRE_TOKEN              # cmd
python -m warframe_lore.discord.main        # --token ...   ou   --ws ws://...
```

Imported via console script (si installé) : `loremaster`.

## 4. Vérifier

- Dans Discord, taper un message sur un canal où le bot est présent → Oracle
  répond en direct (le message s'édite token par token).
- `!reset` relance une session vierge (historique du canal vidé).

## Dépannage

- **Aucune réponse** : vérifier que LM Studio répond (`/v1/models`), que l'API
  ENGRAM tourne sur le bon port et que l'URL WS correspond (`ENGRAM_WS_URL`).
- **Modèle lent / vide** : utiliser un modèle non-raisonant (Llama-3.2-3B)
  plutôt que Qwen3 (raisonnement long avant réponse) ; surchargeable via
  `ENGRAM_CHAT_MODEL` côté serveur ENGRAM.

## Architecture (SOLID)

| Fichier | Rôle |
|---|---|
| `config.py` | `DiscordConfig` (token, WS, préfixe) |
| `gateway.py` | `RoleplayGateway` — connexion WS par canal, diffusion des tokens |
| `bot.py` | `LoreMasterBot` — `discord.Client`, routing des messages |
| `main.py` | entry point console |