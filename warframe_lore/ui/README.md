# `ui` Layer — Local Web Interface

Responsibility: read megafiles `out/*.json` (read-only, no network access)
and serve them via a local **mini HTTP server** (stdlib) for a dark-themed
lore navigation interface — launched via `cephalon ui`.

## Contents

| File | Role |
|---|---|
| `server.py` | `LoreStore`, `main`, `serve_forever`: stdlib server, `gzip`-enabled, `python -m warframe_lore.ui.server --port …` |
| `handlers.py` | `ApiHandler` (BaseHTTPRequestHandler): routes `/`, `/api/stats`, `/api/kim`, `/api/search`, `/api/media`… |
| `store.py` | `LoreStore`: loads/reads megafiles, full-text index, stats |
| `dialogue.py` | Parsing/normalization of KIM conversations for display |
| `dialogue_graph.py` | Tree graph of conversations (flowchart) |
| `dialogue_script.py` | Script rendering (sequence, speakers, choices) |
| `patch_notes.py` | Patch notes traversal |
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

`dist/cephalon-ui.exe` (PyInstaller, see root README) bundles `launch_ui.py`
+ `warframe_lore/ui/static/`; it reads the `out/` folder from the current
directory.
