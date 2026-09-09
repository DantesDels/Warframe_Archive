# `cleaner` Layer — Cleaning

Responsibility: transform raw **Wikitext** into **clean Markdown for LLMs**
(noise removed, canon detected, dialogues normalized).

## Contents

The package is organized by theme (one module = one responsibility):

| Module | Role |
|---|---|
| `config.py` | `CleanerConfig`: loads rules from `config/cleaner_config.json` |
| `preprocessing.py` | Purge of raw content (comments, tables, code) + `mwparserfromhell` parsing |
| `html.py`, `blocks.py` | Sanitization: HTML conversion, files/images, transclusion |
| `templates/` | MediaWiki templates subpackage: `noise.py` (noise + fallback), `render.py` (quote, spoiler, canon), `signal.py` (inline canon/non-canon detection) |
| `links.py`, `markup.py` | Link and Markdown normalization (bold/italic…) |
| `dialogue_lines.py`, `bullets.py`, `headings.py` | Dialogues (`> **Name:** …`), lists, Markdown headings |
| `footers.py`, `audio.py`, `kim_instructions.py` | Removal of footer noise, audio files, KIM dialogue instructions |
| `sections.py`, `sections_classify.py`, `polish.py` | Filtering of gameplay vs lore blocks, empty galleries, blank lines |
| `pipeline.py` | `WikitextCleaner`: orchestrates everything (single entry point) + `CleanOutput` |

## Externalized Rules

Cleaning constants live in `config/cleaner_config.json` and are injected
into `CleanerConfig` (Dependency Injection, SOLID). Edit the rules without
touching the code.

```jsonc
// config/cleaner_config.json
{
  "templates": { "noise_substrings": [...], "audio": [...] },
  "sections":  { "gameplay_exclude": [...], "lore_keep": [...] },
  "speculation": { "non_canon_templates": [...], "marker_non_canon": "..." }
}
```

## Canon

- Inline detection via `templates/signal.py` (`{{Speculation}}`, `{{Canon}}`…);
  the final page-level status is computed by the scraper (cross-referenced with
  `Category:Speculation`) and merged by `merge_canon_status()` (output layer),
  which retains the most cautious status.

## Dialogues

Dialogues are normalized into Markdown blockquotes `> **Name:** speech`,
the format expected by the `db` layer (dialogue-mode chunking + `kim_parser`).

## Usage

```python
from warframe_lore.cleaner import WikitextCleaner

cleaner = WikitextCleaner()
result = cleaner.clean(wikitext_raw)     # CleanOutput(markdown, …)
markdown = result.markdown
```
