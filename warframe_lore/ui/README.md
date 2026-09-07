# Couche `ui` — Interface web locale

Responsabilité : lire les megafiles `out/*.json` (lecture seule, aucun accès
réseau) et les servir via un mini **serveur HTTP local** (stdlib) pour une
interface sombre de navigation du lore — lancée par `cephalon ui`.

## Contenu

| Fichier | Rôle |
|---|---|
| `server.py` | `LoreStore`, `main`, `serve_forever` : serveur stdlib, `gzip`-activé, `python -m warframe_lore.ui.server --port …` |
| `handlers.py` | `ApiHandler` (BaseHTTPRequestHandler) : routes `/`, `/api/stats`, `/api/kim`, `/api/search`, `/api/media`… |
| `store.py` | `LoreStore` : charge/relie les megafiles, index plein texte, stats |
| `dialogue.py` | parsing/normalisation des conversations KIM pour l'affichage |
| `dialogue_graph.py` | graphe arborescent des conversations (flowchart) |
| `dialogue_script.py` | rendu du script (séquence, locuteurs, choix) |
| `patch_notes.py` | parcours des notes de patch |
| `static/` | `app.js` + `styles.css` (interface sombre) |

## Endpoints

| Route | Rôle |
|---|---|
| `/` | interface (assets statiques) |
| `/api/stats` | statistiques globales + cartes des buckets |
| `/api/kim` | conversations KIM structurées (par locuteur) |
| `/api/search?q=…` | recherche plein texte dans tout le contenu |
| `/api/media` | index des images pertinentes (portraits, objets) |
| `/api/image?file=…` | PNG mis en cache (`out/media/`, téléchargement à la demande) |

## Utilisation

```bash
python -m warframe_lore.ui.server --port 50888 --no-browser   # direct
cephalon ui --port 8123                                       # via la CLI
```

## Exe autonome

`dist/cephalon-ui.exe` (PyInstaller, cf. README racine) empaquete `launch_ui.py`
+ `warframe_lore/ui/static/` ; il lit le dossier `out/` du répertoire courant.