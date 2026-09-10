"""Timeline curated data (Warframe lore, eternalism).

Static, deterministic hierarchy: ``era`` (roots) -> ``era``/``quest`` ->
``fragment`` (leaves).  ``has_children`` is derived from ``parent_id``,
which lets the frontend lazy-load by depth: roots first, then
``/api/timeline?parent_id={id}``.

Causality: the Orokin Empire roots divide between the main path
(Old War -> Origin System) and the paradox branch (Zariman), which bursts
into Duviri and 1999 — never sequentially.  In the Origin System,
Octavia's Anthem follows The War Within and The Sacrifice succeeds it.
"""

from __future__ import annotations

# Each node: id, parent_id, label, kind, year, note
NODES: list[dict] = [
    # ------------------------------------------------------------ ères (racines)
    {
        "id": "era-orokin", "parent_id": None,
        "label": "L'Empire Orokin", "kind": "era", "year": "Le Premier Monde",
        "note": "Ballas, les Sentients et la Chute. L'Empire se divise : le "
                "cheminement principal vers l'Ancienne Guerre et la branche "
                "paradoxale de la Zariman.",
    },
    {
        "id": "era-old-war", "parent_id": "era-orokin",
        "label": "L'Ancienne Guerre", "kind": "era", "year": "Ère Orokin",
        "note": "L'Empire Orokin, les Sentients et la Guerre qui a aveuglé "
                "le Système. L'Opérateur s'éveille de ce cauchemar.",
    },
    {
        "id": "era-origin", "parent_id": "era-old-war",
        "label": "Le Système d'Origine", "kind": "era", "year": "Présent",
        "note": "Les Tenno face à la Renaissance du Système. Toutes les "
                "grandes quêtes contemporaines en découlent.",
    },
    {
        "id": "era-zariman", "parent_id": "era-orokin",
        "label": "La Zariman", "kind": "era",
        "year": "Système d'Origine · Paradoxe",
        "note": "Le manifeste du Vide : le vaisseau, ses enfants et le voyage "
                "qui n'a jamais eu lieu. Cette branche éclate vers Duviri "
                "(Drifter) et 1999 (Albrecht).",
    },
    # -------------------------------------------------- mondes-paradoxes fusionnés
    # era-quête fusionnés : "L'An 1999" + quête "1999" -> node-1999 ;
    # "Duviri" + quête "The Duviri Paradox" -> node-duviri. Un seul nœud,
    # jamais d'îlot en doublon. Les fragments pendent directement sous l'ère.
    {
        "id": "node-1999", "parent_id": None,
        "label": "L'An 1999", "kind": "era", "year": "Paradoxe",
        "note": "Höllvania, la veille de l'an 1999 : la quête '1999', ses "
                "fragments et un siècle figé qui n'aboutit qu'au Néant.",
    },
    {
        "id": "node-duviri", "parent_id": None,
        "label": "Duviri", "kind": "era", "year": "Royaume paradoxal",
        "note": "Le drame du Drifter pris dans la Spirale infinie entre le "
                "Vide et la réalité, quête 'The Duviri Paradox' incluse.",
    },
    # ------------------------------------------------------------ quêtes : Système d'Origine (chemin principal)
    {
        "id": "q-sacrifice", "parent_id": "era-origin",
        "label": "The Sacrifice", "kind": "quest",
        "note": "Excalibur Umbra, Ballas et le dernier secret des Orokin. "
                "Découle de l'Octavia's Anthem.",
    },
    {
        "id": "q-octavia", "parent_id": "era-origin",
        "label": "Octavia's Anthem", "kind": "quest",
        "note": "Le Mandachorde et l'Étoile chantée de Maprico. Suit la "
                "Guerre Intérieure, précède The Sacrifice.",
    },
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
        "id": "q-whispers", "parent_id": "era-origin",
        "label": "Whispers in the Walls", "kind": "quest",
        "note": "Albrecht Entrati, le Requiem et la cavité dans les "
                "fondations de la réalité.",
    },
    # ------------------------------------------------------------ quêtes : Zariman (branche paradoxale)
    {
        "id": "q-zariman", "parent_id": "era-zariman",
        "label": "Angels of the Zariman", "kind": "quest",
        "note": "Le vaisseau-manifestation et le prix du voyage dans le Vide.",
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
    # ------------------------------------------------------------ quêtes : node-1999 (ère fusionnée)
    {
        "id": "q-hex", "parent_id": "node-1999",
        "label": "The Hex", "kind": "quest",
        "note": "Les six, la KIM et le lien qui défie les boucles.",
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
    {"id": "f-1999-hollvania", "parent_id": "node-1999",
     "label": "Höllvania · veille de 1999", "kind": "fragment"},
    {"id": "f-1999-indifference", "parent_id": "node-1999",
     "label": "Le Néant approche", "kind": "fragment"},
    {"id": "f-hex-kim", "parent_id": "q-hex",
     "label": "La KIM · les Liens", "kind": "fragment"},
    {"id": "f-duviri-throne", "parent_id": "node-duviri",
     "label": "Le Trône du Drifter", "kind": "fragment"},
    {"id": "f-duviri-thrax", "parent_id": "node-duviri",
     "label": "La Spirale de Duviri", "kind": "fragment"},
]

# Edges (Eternalism), keyed by the parent that loads them (lazy fetch).
# ``paradox: True``  -> dashed flow (Duviri / 1999 / New War / Zariman).
# ``paradox: False`` -> linear causality (sequel quests).
EDGES: dict[str, list[dict]] = {
    # L'Empire se divise : la branche paradoxale de la Zariman éclate vers
    # Duviri (Drifter) et 1999 (Albrecht) — jamais séquentiels.
    "era-orokin": [
        {"source": "era-orokin", "target": "era-zariman",
         "label": "Paradoxe d'éternisme", "paradox": True},
        {"source": "era-zariman", "target": "node-duviri",
         "label": "Le Drifter", "paradox": True},
        {"source": "era-zariman", "target": "node-1999",
         "label": "Albrecht Entrati", "paradox": True},
    ],
    # Causalité linéaire : Octavia's Anthem suit The War Within,
    # The Sacrifice en découle. Le Portail du Drifter reste paradoxal.
    "era-origin": [
        {"source": "q-within", "target": "q-octavia",
         "label": "Après la Guerre Intérieure", "paradox": False},
        {"source": "q-octavia", "target": "q-sacrifice",
         "label": "La vérité sur Umbra", "paradox": False},
        {"source": "q-new-war", "target": "node-duviri",
         "label": "Portail du Drifter", "paradox": True},
    ],
}