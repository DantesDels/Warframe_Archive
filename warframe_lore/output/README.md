# Couche `output` — Export

Responsabilité : formater la donnée finale pour les consommateurs (moteurs LLM,
notebooks, RAG) sous forme de **megafiles JSON** par bucket.

## Contenu

| Fichier | Rôle |
|---|---|
| `models.py` | `OutputEntry`, `MegafileMetadata`, `CanonStatus`, `build_output_entry`, `merge_canon_status` |
| `writer.py` | `MegafileManager` : écrit un fichier JSON par bucket dans `out/` |

## Modèle de sortie

Chaque entrée expose (entre autres) :

- `title` — titre de la page wiki
- `content_markdown` — contenu nettoyé (Markdown prêt pour LLM)
- `canon_status` — `canon` / `speculation` / `community_theory`
- `source_url` — URL de la page source
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

entry = build_output_entry(title=..., content_markdown=...,
                           canon_status=CanonStatus.CANON, ...)
manager = MegafileManager(output_dir="out")
manager.write_bucket(bucket_id="Lore_Quetes", entries=[entry])
```