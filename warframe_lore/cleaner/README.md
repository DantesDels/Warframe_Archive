# Couche `cleaner` — Nettoyage

Responsabilité : transformer le **Wikitext** brut en **Markdown propre pour
LLM** (bruit supprimé, canon détecté, dialogues normalisés).

## Contenu

Le paquet est organisé par thème (un module = une responsabilité) :

| Module | Rôle |
|---|---|
| `config.py` | `CleanerConfig` : charge les règles depuis `config/cleaner_config.json` |
| `preprocessing.py` | purge destinée du brut (commentaires, tables, code) + parse `mwparserfromhell` |
| `html.py`, `blocks.py` | assainissement : conversion HTML, fichiers/images, transclusion |
| `templates/` | sous-paquet templates MediaWiki : `noise.py` (bruit + fallback), `render.py` (quote, spoiler, canon), `signal.py` (détection canon/non-canon inline) |
| `links.py`, `markup.py` | normalisation des liens et du markdown (gras/italique…) |
| `dialogue_lines.py`, `bullets.py`, `headings.py` | dialogues (`> **Nom:** …`), listes, titres Markdown |
| `footers.py`, `audio.py`, `kim_instructions.py` | suppression du bruit de pied de page, fichiers audio, instructions de dialogue KIM |
| `sections.py`, `sections_classify.py`, `polish.py` | filtrage des blocs gameplay vs lore, galeries vides, lignes blanches |
| `pipeline.py` | `WikitextCleaner` : orchestre le tout (un seul point d'entrée) + `CleanOutput` |

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

- Détection inline via `templates/signal.py` (`{{Speculation}}`, `{{Canon}}`…) ;
  le statut final au niveau page est calculé par le scraper (croisement avec
  `Category:Speculation`) et fusionné par `merge_canon_status()` (couche
  `output`), qui retient le statut le plus prudent.

## Dialogues

Les dialogues sont normalisés en blocquotes Markdown `> **Nom:** parole`,
format attendu par la couche `db` (chunking mode dialogue + `kim_parser`).

## Usage

```python
from warframe_lore.cleaner import WikitextCleaner

cleaner = WikitextCleaner()
result = cleaner.clean(wikitext_raw)     # CleanOutput(markdown, …)
markdown = result.markdown
```