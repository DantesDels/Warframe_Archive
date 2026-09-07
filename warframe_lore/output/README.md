# Couche `output` — Export

Responsabilité : formater la donnée finale pour les consommateurs (moteurs LLM,
notebooks, RAG) sous forme de **megafiles JSON** par bucket.

## Contenu

| Fichier | Rôle |
|---|---|
| `models/` | Modèles, un fichier par classe : `canon_status.py` (`CanonStatus` + `merge_canon_status`), `output_entry.py` (`OutputEntry`), `megafile_metadata.py` (`MegafileMetadata`) |
| `entries.py` | `build_output_entry` : factory conforme au schéma JSON documenté |
| `fusion.py` | `read_existing_entries`, `build_megafile`, `atomic_write_json`, `now_iso_utc` : fusion incrémentale + écriture atomique |
| `writer.py` | `MegafileManager.merge_and_write` : fusion d'un bucket et écriture du megafile dans `out/` |

## Modèle de sortie

Chaque entrée expose (entre autres) :

- `page_title` — titre de la page wiki
- `content_markdown` — contenu nettoyé (Markdown prêt pour LLM)
- `canon_status` — `canon` / `speculation` / `community_theory`
- `source` — URL de la page source
- `last_updated` — date de dernière modification (utile au delta)

## Canon

`merge_canon_status(*statuses)` combine plusieurs statuts (pages ou versions)
et retient le **plus prudent** :
`community_theory` > `speculation` > `canon`.

Cela permet à un RAG d'ignorer les théories des joueurs quand on cherche du
canon strictement officiel.

## Usage

```python
from warframe_lore.output import MegafileManager, build_output_entry, CanonStatus

entry = build_output_entry(
    page_title="Excalibur", category="Warframes",
    touched="2026-09-05T12:00:00Z", content_markdown="# Excalibur\n…",
    canon_status=CanonStatus.CANON, pageid=123,
    source_wiki_url="https://wiki.warframe.com/wiki/",
)
manager = MegafileManager(output_dir="out")
manager.merge_and_write(
    filename="Lore_Warframes.json", bucket_title="Warframes",
    new_entries=[entry], metadata_note="…", live_titles={"Excalibur"},
)
```