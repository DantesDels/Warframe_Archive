"""Timeline curated data (Warframe lore, eternalism).

Static, deterministic hierarchy: ``era`` (roots) -> ``quest`` ->
``fragment`` (leaves).  ``has_children`` is derived from ``parent_id``,
which lets the frontend lazy-load by depth: roots first, then
``/api/timeline?parent_id={id}``.
"""

from __future__ import annotations

# Each node: id, parent_id, label, kind, year, note
NODES: list[dict] = [
    # ------------------------------------------------------------ ères (racines)
    {
        "id": "era-old-war", "parent_id": None,
        "label": "L'Ancienne Guerre", "kind": "era", "year": "Ère Orokin",
        "note": "L'Empire Orokin, les Sentients et la Guerre qui a aveuglé "
                "le Système. L'Opérateur s'éveille de ce cauchemar.",
    },
    {
        "id": "era-origin", "parent_id": None,
        "label": "Le Système d'Origine", "kind": "era", "year": "Présent",
        "note": "Les Tenno face à la Renaissance du Système. Toutes les "
                "grandes quêtes contemporaines en découlent.",
    },
    {
        "id": "era-1999", "parent_id": None,
        "label": "L'An 1999", "kind": "era", "year": "Paradoxe",
        "note": "Höllvania, la veille de l'an 1999 : un siècle figé qui "
                "n'aboutit qu'au Néant. Paradoxe d'éternisme.",
    },
    {
        "id": "era-duviri", "parent_id": None,
        "label": "Duviri", "kind": "era", "year": "Royaume paradoxal",
        "note": "Le drame du Drifter, pris dans la Spirale infinie entre le "
                "Vide et la réalité.",
    },
    # ------------------------------------------------------------ quêtes : Ancienne Guerre
    {
        "id": "q-sacrifice", "parent_id": "era-old-war",
        "label": "The Sacrifice", "kind": "quest", "year": "Flashback Orokin",
        "note": "Excalibur Umbra, Ballas et le dernier secret des Orokin.",
    },
    {
        "id": "q-octavia", "parent_id": "era-old-war",
        "label": "Octavia's Anthem", "kind": "quest",
        "note": "Le Mandachorde et l'Étoile chantée de Maprico.",
    },
    # ------------------------------------------------------------ quêtes : Système d'Origine
    {
        "id": "q-vors", "parent_id": "era-origin",
        "label": "Vor's Prize", "kind": "quest",
        "note": "Les Tenno renaissent : Lotus, Vor et la première entaille "
                "dans le Système.",
    },
    {
        "id": "q-second", "parent_id": "era-origin",
        "label": "The Second Dream", "kind": "quest",
        "note": "Le fœtus spectral : la vérité sur les Tenno, les Sentients "
                "et l'éveil de l'Opérateur.",
    },
    {
        "id": "q-within", "parent_id": "era-origin",
        "label": "The War Within", "kind": "quest",
        "note": "Les Reines éternelles, la Kuva et l'héritage Orokin du "
                "Transférance.",
    },
    {
        "id": "q-harrow", "parent_id": "era-origin",
        "label": "Chains of Harrow", "kind": "quest",
        "note": "Rell, silence et les chaînes du Red Veil.",
    },
    {
        "id": "q-new-war", "parent_id": "era-origin",
        "label": "The New War", "kind": "quest", "year": "Aboutissement",
        "note": "La guerre totale contre Ballas, les Sentients et le pacte "
                "du Drifter.",
    },
    {
        "id": "q-zariman", "parent_id": "era-origin",
        "label": "Angels of the Zariman", "kind": "quest",
        "note": "Le vaisseau-manifestation et le prix du voyage dans le Vide.",
    },
    {
        "id": "q-whispers", "parent_id": "era-origin",
        "label": "Whispers in the Walls", "kind": "quest",
        "note": "Albrecht Entrati, le Requiem et la cavité dans les "
                "fondations de la réalité.",
    },
    {
        "id": "q-jade", "parent_id": "era-origin",
        "label": "Jade Shadows", "kind": "quest",
        "note": "Une lumière tombée du ciel et son enfant.",
    },
    {
        "id": "q-deimos", "parent_id": "era-origin",
        "label": "Heart of Deimos", "kind": "quest",
        "note": "Le cœur de l'Infestation, battant sous Deimos.",
    },
    # ------------------------------------------------------------ quêtes : 1999
    {
        "id": "q-1999", "parent_id": "era-1999",
        "label": "1999", "kind": "quest",
        "note": "L'équipe qui tenait la ligne pendant la veille de la chute "
                "de Höllvania.",
    },
    {
        "id": "q-hex", "parent_id": "era-1999",
        "label": "The Hex", "kind": "quest",
        "note": "Les six, la KIM et le lien qui défie les boucles.",
    },
    # ------------------------------------------------------------ quêtes : Duviri
    {
        "id": "q-duviri", "parent_id": "era-duviri",
        "label": "The Duviri Paradox", "kind": "quest",
        "note": "Le Drifter apprend à converser avec ses prisons, une rechute "
                "à la fois.",
    },
    # ------------------------------------------------------------ fragments
    {"id": "f-sacrifice-excal", "parent_id": "q-sacrifice",
     "label": "Excalibur Umbra · Ballas", "kind": "fragment"},
    {"id": "f-sacrifice-lotus", "parent_id": "q-sacrifice",
     "label": "Le Lotien survivant", "kind": "fragment"},
    {"id": "f-octavia-maprico", "parent_id": "q-octavia",
     "label": "Mandachorde de Maprico", "kind": "fragment"},
    {"id": "f-second-sentients", "parent_id": "q-second",
     "label": "Les Sentients · Céphalon", "kind": "fragment"},
    {"id": "f-second-margulis", "parent_id": "q-second",
     "label": "Margulis · l'Enfant guide", "kind": "fragment"},
    {"id": "f-within-queens", "parent_id": "q-within",
     "label": "Les Reines · la Kuva", "kind": "fragment"},
    {"id": "f-within-teshin", "parent_id": "q-within",
     "label": "Teshin · le Dax", "kind": "fragment"},
    {"id": "f-harrow-rell", "parent_id": "q-harrow",
     "label": "Rell · le Red Veil", "kind": "fragment"},
    {"id": "f-whispers-requiem", "parent_id": "q-whispers",
     "label": "Requiem d'Albrecht", "kind": "fragment"},
    {"id": "f-newwar-pact", "parent_id": "q-new-war",
     "label": "Pacte du Drifter", "kind": "fragment"},
    {"id": "f-1999-hollvania", "parent_id": "q-1999",
     "label": "Höllvania · veille de 1999", "kind": "fragment"},
    {"id": "f-1999-indifference", "parent_id": "q-1999",
     "label": "Le Néant approche", "kind": "fragment"},
    {"id": "f-hex-kim", "parent_id": "q-hex",
     "label": "La KIM · les Liens", "kind": "fragment"},
    {"id": "f-duviri-throne", "parent_id": "q-duviri",
     "label": "Le Trône du Drifter", "kind": "fragment"},
    {"id": "f-duviri-thrax", "parent_id": "q-duviri",
     "label": "La Spirale de Duviri", "kind": "fragment"},
]

# Alternative temporal edges (Eternalism) : Duviri / 1999 / New War.
# Drawn as animated dashed SVG paths (``edge-paradox``).
PARADOX_EDGES: list[dict] = [
    {"source": "era-1999", "target": "era-duviri",
     "label": "Boucle temporelle"},
    {"source": "q-1999", "target": "q-duviri", "label": "Le même drame"},
    {"source": "q-new-war", "target": "era-duviri",
     "label": "Portail du Drifter"},
]