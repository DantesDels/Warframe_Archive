# Couche `kim_dm` — Datamine KIM

Responsabilité : le **miroir KIM** (datamine) — les conversations de
l'*Instant Messenger* du jeu (kinemantik etc.), téléchargée depuis la source
officielle, parsée et structurée en conversations hiérarchisées.

## Contenu

| Fichier | Rôle |
|---|---|
| `__init__.py` | API publique : `KimDM`, `WIKI_PAGE_MAP`, `parse_dialogue_file`, `mirror_kim_dm` |
| `constants.py` | pages KIM connues / mapping |
| `parser.py` | `parse_dialogue_file` : lignes de dialogue → structure (locuteur, choix du joueur) |
| `graph.py` | graphe arborescent des conversations (ancrage racine, choix rattachés au PNJ) |
| `traversal.py` | parcours du graphe (layout dagre TB/UL) |
| `store.py` | persistance / lecture du miroir local |
| `mirror.py` | téléchargement du miroir officiel |

## Usage

```bash
cephalon kim-dm               # met à jour le miroir
```

Programmatique :

```python
from warframe_lore.kim_dm import KimDM, parse_dialogue_file

dialogue = parse_dialogue_file("§ Amir — Conversation.md")
dm = KimDM(...)
```

L'interface web (`cephalon ui`) consume ce format pour afficher les
conversations structurées par locuteur et le graphe en flowchart.