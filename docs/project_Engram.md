# Architecture Technique : Cephalon Archive

Ce document détaille l'infrastructure complète du projet, divisée en cinq piliers fondamentaux. L'architecture est conçue pour lier une base de données vectorielle complexe issue du moteur Evolution Engine à de multiples interfaces (Bureau, Discord) via un backend IA temps réel.

## 1. Orchestration & Déploiement

L'infrastructure repose sur une séparation stricte entre l'inférence matérielle lourde et la logique applicative.

* **Inférence Locale (Hôte) :** Le modèle LLM (Qwen3.8-27B) s'exécute nativement sur la machine hôte via LM Studio. Cela garantit un accès exclusif et non bridé à la VRAM du GPU. Le serveur expose une API REST compatible OpenAI sur `localhost`.
* **Conteneurisation (Docker Compose) :** Les services applicatifs sont isolés dans des conteneurs distincts pour assurer la reproductibilité de l'environnement :
  * Base de données PostgreSQL (avec extension `pgvector`).
  * Backend API (Python/FastAPI).
  * Service autonome du Bot Discord.

## 2. Pipeline ETL (Extract, Transform, Load)

Le cycle de vie de la donnée, depuis les sources des développeurs jusqu'à l'injection vectorielle.

* **Extraction (Scraper) :** Scripts automatisés ciblant le Wikitext brut et les exports officiels du jeu.
* **Transformation (Parser) :** Traitement algorithmique des fichiers `.dialogue.json`. Le parser croise ces données avec les dictionnaires de localisation (`en.json`) pour reconstituer l'arborescence causale exacte des discussions (nœuds, arêtes, conditions).
* **Vectorisation (Embedding) :** Découpage du lore et des dialogues en *chunks* contextuels. Utilisation d'un modèle d'embedding multilingue (ex: BAAI/bge-m3) pour stocker les vecteurs dans PostgreSQL (`pgvector`), permettant d'interroger des données anglophones avec des requêtes francophones.

## 3. Backend Central (FastAPI & RAG)

Le microservice jouant le rôle de routeur intelligent entre la base de données, LM Studio, et les clients.

* **Endpoint Documentaire (HTTP POST) :** Gère le RAG encyclopédique. Recherche par similarité cosinus dans `pgvector`, construction du *Super-Prompt* incluant les sources, et renvoi structuré des réponses.
* **Endpoint Roleplay (WebSockets) :** Gère les terminaux KIM. Maintient une connexion bidirectionnelle pour streamer les tokens générés par le LLM en temps réel.
* **Gestion d'État (Sliding Window) :** Cache asynchrone conservant les derniers échanges de la session active pour doter l'IA d'une mémoire conversationnelle à court terme.

## 4. Application Client (UI/UX)

L'évolution de l'interface web vers une application de bureau native isolée.

* **Wrapper Desktop :** Encapsulation de l'interface Vue.js via un framework de bureau (Tauri ou Electron) pour un fonctionnement logiciel local.
* **Module Encyclopédique :** Interfaces statiques optimisées pour la consultation du Codex, des Fragments, des Quêtes et de l'Univers.
* **Simulateur KIM :** Interface de messagerie réactive. Consomme le flux WebSocket pour afficher les messages de manière organique, incluant des indicateurs d'état asynchrones (ex: "Amir est en train d'écrire...").

## 5. Le Loremaster (Bot Discord)

Un client autonome orienté vers la narration et la didactique communautaire.

* **Technologie :** Serveur indépendant (développable en Java via le framework JDA ou en Python).
* **Commandes Slash (`/`) :** Interfaces de commandes intuitives pour interroger l'API centrale sur des périodes, des factions ou des personnages spécifiques.
* **Formatage Avancé :** Utilisation systématique des *Embeds* Discord pour hiérarchiser l'information, afficher les images associées au lore, et lister proprement les sources extraites par le pipeline RAG.