# `ui` Layer — Local Web Interface

Responsibility: read megafiles `out/*.json` (read-only, no network access)
and serve them via a local **mini HTTP server** (stdlib) for a dark-themed
lore navigation interface — launched via `cephalon ui`.

## Contents

| File | Role |
|---|---|
| `server.py` | `LoreStore`, `main`, `serve_forever`: stdlib server, `gzip`-enabled, `python -m warframe_lore.ui.server --port …` |
| `patch_notes.py` | Patch notes traversal |
| **`http/`** | `handlers.py` (`ApiHandler`: routes `/`, `/api/stats`, `/api/kim`, `/api/search`, `/api/media`…), `httpio.py` (Gzip/ETag transport) |
| **`data/`** | `store.py` (`LoreStore` facade), `megafiles.py` (incremental `out/*.json` loading), `search.py` (full-text index) |
| **`dialogue/`** | `dialogue.py` (facade), `dialogue_graph.py` (tree graph), `dialogue_script.py` (script rendering), `refs.py`, `sections.py`, `kim_view.py` |
| `static/` | `app.js` + `styles.css` (dark interface) |

## Endpoints

| Route | Role |
|---|---|
| `/` | Interface (static assets) |
| `/api/stats` | Global statistics + bucket cards |
| `/api/kim` | Structured KIM conversations (by speaker) |
| `/api/search?q=…` | Full-text search across all content |
| `/api/media` | Index of relevant images (portraits, objects) |
| `/api/image?file=…` | Cached PNG (`out/media/`, on-demand download) |

## Usage

```bash
python -m warframe_lore.ui.server --port 50888 --no-browser   # direct
cephalon ui --port 8123                                       # via CLI
```

## Standalone Executable

`dist/cephalon-ui.exe` (PyInstaller, see root README) bundles
`packaging/launch_ui.py` + `warframe_lore/ui/static/`; it reads the `out/`
folder from the current directory.
