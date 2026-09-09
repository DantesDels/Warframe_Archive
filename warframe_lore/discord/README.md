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

Surcharges par variables d'environnement, fichier `.env` à la racine du projet
(lu automatiquement, sans dépendance — uniquement si la variable n'existe pas
déjà dans le shell) ou arguments CLI :

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
# 1) racine du projet : créer .env (secret, non versionné)
#    DISCORD_TOKEN=MTE...  (token du bot depuis le portail Discord)

# 2) depuis la racine du projet (ENGRAM tourne sur :8000)
cephalon bot run
# (équivalent : python -m warframe_lore.discord.main, ou l'alias CLI « -bot run »)

# options utiles — canal dédié + logs verbeux :
cephalon bot run --channels <ID> --verbose
# ou, si un token doit primer sur .env :
$env:DISCORD_TOKEN = "VOTRE_TOKEN"    # PowerShell
cephalon bot run
```

Disponible aussi via le console script `loremaster`.

## 3. Sécurité et hostilité (anti-attaquant)

- **Détection déterministe** (`engram/rag/probes.py`) : injection SQL,
  élévation de privilèges (`is_admin`, `permissions`…), mentions tierces
  `<@id>` → rejet **sans appeler le LLM** avec la chaîne exacte
  `JAILBREAK_REJECT` (HTTP `POST /v1/rag` **et** WS `/v1/roleplay`).
- **Rate limit** : fenêtre glissante par IP (HTTP 429 / fermeture WS 1008) +
  garde anti-spam coté bot (`guards.py` : cooldown utilisateur, plafond par
  canal, blocage temporaire sur insistance).
- **Persona hostile par attaquant** : dès qu'une sonde est détectée
  (`bot.py._handle_probe`), la session WS de **cet utilisateur** est basculée
  sur le persona anti-agression `persona/oracle_hostile` (éditable) via la
  trame `{"type":"persona","mode":"hostile"}` (`gateway.set_persona`). Les
  autres utilisateurs et la session normale du salon ne sont pas affectés.
- **Rédemption par excuses** : le bot insiste pour obtenir des excuses
  (`_insist`) ; la détection déterministe `is_apology` (`hostile_link.py`,
  marqueurs : *pardon, excusez-moi, désolé, sorry, mea culpa…*) ramène le
  persona oracle et ferme la session hostile (`_forgive`).

## 5. Vérifier

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
| `config.py` | `DiscordConfig` (token, WS, préfixe, canaux autorisés) |
| `gateway.py` | `RoleplayGateway` — connexion WS par canal, diffusion des tokens, `set_persona` (bascule personne hostile) |
| `streamer.py` | `MessageStreamer` — édition du message avec buffering (anti 429) |
| `guards.py` | `BurstGuard` — anti-spam (cooldown utilisateur, plafond par canal, blocage) |
| `hostility.py` | escalade ciblée (`reply_for`, niveau 0→2) + `HostilityTracker` |
| `hostile_link.py` | session hostile par attaquant (`is_apology`, bascule/retour de persona) |
| `bot.py` | `LoreMasterBot` — `discord.Client`, routing, détection de sondes (`_handle_probe`/`_insist`/`_forgive`) |
| `main.py` | entry point console (`launch_bot` partagé avec le CLI `cephalon bot run`) |