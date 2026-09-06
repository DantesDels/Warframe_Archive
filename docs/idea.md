# Roadmap et Vision — Projet "Cephalon Archive"

**Objectif :** Créer la base de connaissances ultime sur l'univers de Warframe,
exploitable par des Modèles de Langage (LLM) et des applications RAG
(Retrieval-Augmented Generation).

---

## 1. Modularité : Les Fondations du Projet

Le projet repose sur une architecture découplée (voir `docs/architecture.md`).
Chaque composant a une responsabilité unique, ce qui permet de faire évoluer une
brique sans casser le reste du système.

- **Extraction (`api`) :** gère uniquement la communication avec l'API
  MediaWiki (interface `BaseSource`). Si l'API change, seul ce module est impacté.
- **Nettoyage (`cleaner`) :** transforme le Wikitext en Markdown propre, avec
  filtrage du bruit, des sections gameplay et de la canonique.
- **Synchronisation (`sync`) :** assure le mode "Delta" (ne traiter que les
  nouveautés), relayé par la suite à la base SQL.
- **Persistance SQL (`db`) :** PostgreSQL normalisé (3NF), embeddings pgvector,
  chunking RAG (`ChunkManager`), delta via base.
- **Export (`output`) :** formate la donnée finale (megafiles JSON par bucket,
  avec `canon_status`).
- **Évolutivité des sources :** l'architecture permet d'ajouter facilement de
  nouveaux "Clients" (ex: `RedditScraper` pour r/Warframe, `ForumScraper` pour
  les patch notes officiels) qui viendront se brancher sur le même pipeline.

## 2. Scalabilité : Industrialisation et Passage à l'Échelle

Pour dépasser les limites d'un simple carnet personnel et créer un outil
utilisable massivement, l'architecture peut évoluer vers des standards Cloud et
Big Data.

- **Scraping HTTP robuste (fait) :** `requests` + retries/backoff/politesse
  intégrés ; asynchrone côté base (SQLAlchemy 2.0 async + asyncpg). Un passage
  complet en `aiohttp` permettrait de paralléliser davantage l'extraction.
- **Base de Données Vectorielle (amorcé) :** la couche `db` stocke désormais
  chaque chunk avec son embedding `vector(384)` (pgvector). Le réseau JSON n'est
  plus seul : les recherches sémantiques pourront se faire directement en SQL.
- **Pipeline CI/CD (à venir) :** déploiement sur GitHub Actions ou AWS Lambda
  avec déclencheur cron ; le script s'exécute de manière autonome (par exemple
  chaque mardi après les mises à jour de Warframe) et met à jour la base sans
  intervention humaine.

## 3. Optimisations Techniques (Data Prep)

La qualité de la donnée pour les LLM est un axe produit permanent.

- **Chunking Intelligent (fait, Phase 2.5) :** `ChunkManager` découpe les
  longues pages en blocs sémantiques (target 1200c, dialogues 2500c) en
  respectant les titres (`##`/`###`) et les paragraphes. Deux passes :
  structurelle (headers en métadonnées) + récursive avec chevauchement, plus un
  mode dédié aux dialogues KIM/JDR/Quêtes (`speakers` en métadonnées).
- **Enrichissement par Métadonnées (partiel) :** chaque chunk porte des
  métadonnées exploitables (hiérarchie de titres, locuteurs) stockées en JSONB
  et filtrables par l'index GIN avant envoi au LLM. Une passe NLP de tagging
  automatique (ex: `Tags: [Grineer, Clonage, Tyl Regor]`) reste possible.
- **Détection du canon (fait) :** chaque entrée expose `canon_status`
  (`canon` / `speculation` / `community_theory`) détecté via
  `Category:Speculation` et les marqueurs inline ; `merge_canon_status` retient
  le statut le plus prudent.
- **Gestion du Multimédia (à venir) :** extraction systématique des URL
  d'images (portraits, cartes, symboles) pour que les futures interfaces
  affichent l'image du personnage avec sa réponse textuelle.

## 4. Cas d'Usage Actuels (MVP - Produit Minimum Viable)

Avec la base JSON (megafiles) et la couche SQL (pgvector + JSONB) injectées dans
un outil type NotebookLM ou un pipeline RAG, voici ce qui est déjà réalisable :

- **L'Oracle de Warframe :** un assistant capable de croiser les textes du jeu
  pour répondre à des questions complexes sans "halluciner" (ex: "Quelle est la
  chronologie de la rébellion de Parvos Granum ?"), en filtrant le canon.
- **Maître du Jeu Virtuel (GM) :** en utilisant spécifiquement les données du
  JDR "Fables & Frontiers" et du système KIM (mode dialogue dédié, locuteurs
  conservés), l'IA peut incarner Amir et faire jouer des campagnes inédites avec
  les règles exactes de cet univers.
- **Audit de Lore :** l'IA peut analyser l'intégralité du texte pour repérer les
  incohérences scénaristiques ou les intrigues non résolues (plot holes) laissées
  par Digital Extremes au fil des années.

## 5. Évolutions Futures (La Vision à Long Terme)

Une fois la donnée parfaitement structurée et vectorisée, le projet peut
s'ouvrir à des applications tierces via des frameworks comme LangChain ou
LlamaIndex.

- **Application RAG Autonome et Bot Discord :** développement d'un backend
  Python connecté à un Bot Discord ou une interface Web (Streamlit/Vue.js). Les
  joueurs posent une question sur leur serveur, le bot interroge la base
  vectorielle, et l'IA formule la réponse instantanément.
- **Générateur de Contenu Automatisé :** couplage de la base avec des
  générateurs IA vocaux (ElevenLabs) et visuels (Midjourney). L'outil pourrait
  scripter, illustrer et narrer automatiquement des vidéos d'analyse de lore à
  chaque nouvelle mise à jour.
- **Personas IA Interactifs :** création d'agents conversationnels adoptant la
  personnalité psychologique et le vocabulaire exact d'un personnage précis
  (ex: un chatbot "Ballas" qui débate de la philosophie Orokin en utilisant
  exclusivement son style rhétorique extrait du wiki).