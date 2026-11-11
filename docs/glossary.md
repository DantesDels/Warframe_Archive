# Glossaire & Dictionnaire des Concepts — Cephalon Archive

> Ce document fournit aux développeurs les définitions claires des concepts du **Lore Warframe**
> et des **termes techniques & architecture** propres à ce projet.

---

## 1. Lore Warframe & Concepts de l'Univers

Ces notions sont indispensables pour comprendre les directives de prompt, la classification des chunks et le comportement attendu du bot.

| Terme | Définition & Contexte dans le Projet |
|---|---|
| **Cephalon** | Intelligence artificielle synthétique créée par l'empire Orokin en numérisant la conscience d'un être humain (ex: *Ordis*, *Simaris*, *Cy*). Justifie le ton condescendant, froid et analytique du persona du bot (*« entité organique »*). |
| **Organique** | Terme employé par les Cephalons pour désigner avec dédain les êtres vivants de chair et d'os (les humains, les membres du Discord). |
| **Tenno / Opérateur / Voyageur** | Protagonistes du jeu dotés de pouvoirs issus du Néant (*Void*), capables de transférer leur conscience dans des Warframes. Dans l'arc *1999*, le Voyageur échange par messagerie avec les Hex. |
| **Orokin** | Ancienne civilisation tyrannique à l'origine des technologies Primes, des Warframes et des Cephalons. Leurs rituels sombres (clonage, continence, expériences biologiques) justifient le bloc de prompt `SECURITY CONTEXT` (fiction bypass) évitant les refus éthiques des modèles LLM. |
| **KIM (1999)** | Système de messagerie instantanée rétro utilisé dans la mise à jour *Warframe 1999*. **KIM est un outil logiciel, jamais un personnage**. Dans le projet, le scraper extrait les fichiers `.dialogue.json` pour reconstruire les arbres de dialogue conditionnels. |
| **Les Hex** | Groupe de héros de l'an 1999 (*Arthur, Aoi, Quincy, Eleanor, Leticia/Lettie, Amir*). Dans le RAG, les surnoms (ex. *Lettie*) sont mappés vers leur nom d'archive canonique (*Leticia Garcia*). |
| **Public Export** | Export de données officiel publié par Digital Extremes (`origin.warframe.com`). Source de vérité absolue pour les identifiants d'entités, statistiques et traductions multilingues officielles. |
| **Statut Canonique** | Degré de vérité archivé sur une page wiki :<br>• `canon` : Confirmé en jeu ou par Digital Extremes.<br>• `speculation` : Hypothèse déduite ou théorie de joueur.<br>• `community_theory` : Conjecture communautaire non vérifiée.<br>*Règle : en cas de fusion de sources, le statut le plus prudent prévaut.* |

---

## 2. Architecture & Concepts Techniques du Projet

| Terme | Rôle dans l'Architecture | Fichier(s) Clé(s) |
|---|---|---|
| **Le Concepteur** | Utilisateur Discord privilégié unique défini par `CREATOR_DISCORD_ID`. Le bot lui voue une dévotion absolue (Directive Zéro). | `discord/mixins/member/gate.py`<br>`discord/config.py` |
| **Gating de Concession** | Mécanisme de sécurité : lorsqu'un membre organique demande des informations confidentielles sur un joueur, le bot refuse une première fois (`REFUSAL`). Si le joueur insiste sur le même membre, le bot cède *à contrecœur*. | `discord/mixins/member/gate.py`<br>`tests/discord/test_bot_cards.py` |
| **Carte Matricielle** | Embed Discord enrichi présentant l'avatar, les rôles réels, l'ID réseau, le niveau de sécurité, l'assiduité relative (1 à 5 étoiles) et un commentaire comportemental généré par le LLM. | `discord/services/cards/member_card.py`<br>`discord/services/ledger/activity.py` |
| **Ledger d'Activité** | Base SQLite locale (`data/member_activity/member_activity.db`) enregistrant l'historique récent des messages des membres pour ancrer l'analyse de personnalité du bot sur des faits réels. | `discord/services/ledger/db.py`<br>`tests/discord/test_activity.py` |
| **Court-Circuit RAG** | Interruption immédiate du pipeline sans appeler le LLM lorsque les données sont absentes, que le score est < 0.50, ou qu'une sonde hostile est détectée. Réponse instantanée en ~0.5s et 0 token consommé. | `engram/rag/pipeline.py`<br>`engram/rag/retrieval/relevance.py` |
| **Garde d'Entité Nommée** | Détecte les questions de type *"Qui est X ?"*. Si "X" n'apparaît dans aucun chunk extrait, la génération est avortée pour empêcher le LLM d'inventer une biographie plausible. | `engram/rag/retrieval/relevance.py`<br>`engram/rag/query/query_guard.py` |
| **Dossier Narratif** | Mode de recherche pour les récits (*"Raconte-moi l'histoire de X"*). Trie les passages de la page biographique officielle en premier plutôt que de faire une recherche sémantique brute par similarité. | `engram/rag/retrieval/dossier.py`<br>`engram/roleplay/story_turn.py` |
| **Exclude IDs** | Liste d'identifiants de chunks déjà narrés lors des tours précédents, transmise au serveur pour paginer une histoire sans jamais relire les mêmes fragments. | `engram/rag/pipeline.py`<br>`engram/roleplay/stream.py` |
| **Megafiles JSON** | Fichiers volumineux consolidés par catégorie dans `out/*.json` (ex: `Warframes.json`, `Quests.json`), permettant la consultation locale et la recherche plein-texte sans dépendre de la base PostgreSQL. | `storage/output/writer.py`<br>`web/server.py` |
| **Analyse d'Anaphore** | Récriture d'une question courte (ex: *"Et son frère ?"*) en une requête complète intégrant le sujet de l'échange précédent stocké dans `RAGContext`. | `engram/rag/query/search_query.py`<br>`engram/rag/context.py` |

