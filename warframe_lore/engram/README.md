# Couche `engram` — Backend IA & RAG

Responsabilité : exposer la base de connaissances vectorisée et un terminal
Roleplay temps réel, adossés à **LM Studio local** (chat + embedding).

Conçu en respect strict de SOLID (un rôle par module, interfaces injectées par
dépendance inverse) : l'`API` ne dépend jamais d'un stockage ou d'un client
concret — elle consomme des abstractions injectées via le `Container`.

## Contenu

| Fichier / paquet | Rôle |
|---|---|
| `config.py` | `EngramConfig` : URLs DB/LLM, modèles, top_k, fenêtres (surchargeable par env `ENGRAM_*`) |
| `persona.py` | `Persona` : prompt système lu depuis `persona/oracle` (éditable à la volée) |
| `llm/` | `base.py` (interfaces `LLMProvider` / `EmbeddingProvider`), `lmstudio.py` (`LMStudioProvider`, OpenAI-compatible) |
| `rag/` | `retriever.py` (contrat `Retriever` + `RAGHit`), `search.py` (`CosinusSearch` pgvector), `prompt.py` (`PromptBuilder`), `service.py` (`RAGService`) |
| `roleplay/` | `models.py` (`Session`/`Turn`), `window.py` (`SlidingWindow`), `stream.py` (`RoleplayService` streaming) |
| `api/` | `main.py` (FastAPI), `container.py` (composition des services), `schemas.py` (HTTP), `routers/` (`document_rag.py`, `roleplay.py`) |
| `scripts/` | `ingest.py` : ETL megafiles JSON → `lore_chunks` vectorisés |

## Architecture

```
EngramConfig ──► Container (DI) ──┬─► LMStudioProvider (chat + embed)
                                  ├─► CosinusSearch (Retriever pgvector)
                                  ├─► RAGService  → POST /v1/rag
                                  └─► RoleplayService → WS /v1/roleplay
```

Le moteur (`RAGService`) dépend uniquement des abstractions `EmbeddingProvider`,
`Retriever` et `LLMProvider` (inversion de dépendance) — on peut brancher un
autre stockage vectoriel (FAISS, Qdrant…) ou un autre LLM sans toucher au cœur.

## RAG documentaire

1. La question est vectorisée (`bge-m3`, 1024d) via LM Studio ;
2. `CosinusSearch` interroge `lore_chunks.embedding` par similarité cosinus
   pgvector (opérateur `<=>`, index HNSW), limité par `top_k` + `min_score` ;
3. `PromptBuilder` assemble le contexte + la question ;
4. L'LLM génère la réponse, streamée ou en une fois, avec les sources.

## Terminal Roleplay (WebSocket)

`WS /v1/roleplay` : une session par connexion, `SlidingWindow` borne l'historique
(nombre de tours + taille de contexte), le LLM répond **token par token**, la
réponse est enregistrée dans la session après diffusion.

Le persona (prompt système) est chargé depuis `persona/oracle` au démarrage —
modifiable librement puis redémarrez le serveur.

## Installation / Lancement

```bash
# Base PostgreSQL + pgvector (docker-compose racine)
docker compose up -d

# Schéma + ingestion + vectorisation
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

# API
uvicorn warframe_lore.engram.api.main:app --port 8000
```

Requiert LM Studio sur `http://localhost:1234` (chat + embedding), modèles
surchargeables via les variables `ENGRAM_CHAT_MODEL`, `ENGRAM_EMBED_MODEL`,
`ENGRAM_LLM_BASE`.

## Endpoints

| Route | Type | Rôle |
|---|---|---|
| `/health` | GET | état du service |
| `/v1/rag` | POST | RAG documentaire (`{question, stream}`) → réponse + sources |
| `/v1/roleplay` | WS | terminal Oracle, streaming token |
| `/docs`, `/redoc` | GET | documentation interactive |
