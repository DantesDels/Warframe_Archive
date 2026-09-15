# `kim_dm` Layer — KIM Datamine

Responsibility: the **KIM mirror** (datamine) — conversations from the
game's *Instant Messenger* (kinemantik etc.), downloaded from the official
source, parsed and structured into hierarchical conversations.

## Contents

| File | Role |
|---|---|
| `__init__.py` | Public API: `KimDM`, `WIKI_PAGE_MAP`, `parse_dialogue_file`, `mirror_kim_dm` |
| `constants.py` | Known KIM pages / mapping |
| `parser.py` | `parse_dialogue_file`: dialogue lines → structure (speaker, player choice) |
| `graph.py` | Tree graph of conversations (root anchoring, choices attached to NPC) |
| `traversal.py` | Graph traversal (dagre TB/UL layout) |
| `store.py` | Persistence / reading of the local mirror |
| `mirror.py` | Download of the official mirror |

## Usage

```bash
cephalon kim-dm               # updates the mirror
```

Programmatic:

```python
from warframe_lore.kim_dm import KimDM, parse_dialogue_file

dialogue = parse_dialogue_file("§ Amir — Conversation.md")
dm = KimDM(...)
```

The web interface (`cephalon ui`) consumes this format to display
conversations structured by speaker and a flowchart graph.
