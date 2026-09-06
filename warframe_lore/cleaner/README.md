# Couche `cleaner` — Nettoyage

Responsabilité : transformer le **Wikitext** brut en **Markdown propre pour
LLM** (bruit supprimé, canon détecté, dialogues normalisés).

## Contenu

| Fichier | Rôle |
|---|---|
| `preprocessing.py` | strip HTML, commentaires, tables, Lua, transclusion |
| `templates.py` | suppression/rendu des templates MediaWiki (bruit, voir `config/cleaner_config.json`) |
| `sections.py` | filtrage des sections gameplay vs lore (`gameplay_exclude` / `lore_keep`) |
| `formatting.py` | normalisation des liens, markdown, dialogues, headings |
| `pipeline.py` | `WikitextCleaner` : orchestre le tout (un seul point d'entrée) |

## Règles externalisées

Les constantes de nettoyage vivent dans `config/cleaner_config.json` et sont
injectées dans `CleanerConfig` (Dependency Injection, SOLID). Modifiez les
règles sans toucher au code.

```jsonc
// config/cleaner_config.json
{
  "templates": { "noise_substrings": [...], "audio": [...] },
  "sections":  { "gameplay_exclude": [...], "lore_keep": [...] },
  "speculation": { "non_canon_templates": [...], "marker_non_canon": "..." }
}
```

## Canon

- Détection de la page dans `Category:Speculation` → `speculation`.
- Marqueurs inline `[NON-CANON / SPECULATION JOUEUR]` / `[CANON OFFICIEL]`.
- `merge_canon_status()` (couche `output`) retient le statut le plus prudent.

## Dialogues

Les dialogues sont normalisés en blocquotes Markdown `> **Nom:** parole`,
format attendu par la couche `db` (chunking mode dialogue + `kim_parser`).

## Usage

```python
from warframe_lore.cleaner import WikitextCleaner

cleaner = WikitextCleaner()
markdown = cleaner.clean(wikitext_raw)
```