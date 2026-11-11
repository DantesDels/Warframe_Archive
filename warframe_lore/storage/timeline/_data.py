"""Timeline curated data (Warframe lore, eternalism).

Static, deterministic hierarchy: ``era`` (roots) -> ``era``/``quest``/
``character``/``warframe-lore`` -> ``fragment`` leaves.  ``has_children`` is
derived from ``parent_id``, which lets the frontend lazy-load by depth:
roots first, then ``/api/timeline?parent_id={id}``.

Every node carries a ``codex_slug`` (archive article key) or ``None`` for
nodes still unreferenced in the codex.  Weapons are strictly excluded:
the timeline is causal lore, not an armory.

Causality: the Orokin Empire roots divide between the main path
(Old War -> Origin System) and the paradox branch (Zariman), which bursts
into Duviri and 1999 — never sequentially.  In the Origin System,
Octavia's Anthem follows The War Within and The Sacrifice succeeds it.
"""

from __future__ import annotations

# Each node: id, parent_id, label, type, year, note, codex_slug (str | None)
NODES: list[dict] = [
    # ------------------------------ ères (racines)
    {
        "id": "era-orokin", "parent_id": None,
        "label": "L'Empire Orokin", "type": "era", "year": "Le Premier Monde",
        "codex_slug": "empire-orokin",
        "note": "Ballas, les Sentients et la Chute. L'Empire se divise : le "
                "cheminement principal vers l'Ancienne Guerre et la branche "
                "paradoxale de la Zariman.",
    },
    {
        "id": "era-old-war", "parent_id": "era-orokin",
        "label": "L'Ancienne Guerre", "type": "era", "year": "Ère Orokin",
        "codex_slug": "ancienne-guerre",
        "note": "L'Empire Orokin, les Sentients et la Guerre qui a aveuglé "
                "le Système. L'Opérateur s'éveille de ce cauchemar.",
    },
    {
        "id": "era-origin", "parent_id": "era-old-war",
        "label": "Le Système d'Origine", "type": "era", "year": "Présent",
        "codex_slug": "systeme-origine",
        "note": "Les Tenno face à la Renaissance du Système. Toutes les "
                "grandes quêtes contemporaines en découlent.",
    },
    {
        "id": "era-zariman", "parent_id": "era-orokin",
        "label": "La Zariman", "type": "era",
        "year": "Système d'Origine · Paradoxe",
        "codex_slug": "zariman",
        "note": "Le manifeste du Vide : le vaisseau, ses enfants et le voyage "
                "qui n'a jamais eu lieu. Cette branche éclate vers Duviri "
                "(Drifter) et 1999 (Albrecht).",
    },
    # ------------------------------ mondes-paradoxes fusionnés
    # era-quête fusionnés : "L'An 1999" + quête "1999" -> node-1999 ;
    # "Duviri" + quête "The Duviri Paradox" -> node-duviri. Un seul nœud,
    # jamais d'îlot en doublon. Les fragments pendent directement sous l'ère.
    {
        "id": "node-1999", "parent_id": None,
        "label": "L'An 1999", "type": "era", "year": "Paradoxe",
        "codex_slug": "an-1999",
        "note": "Höllvania, la veille de l'an 1999 : la quête '1999', ses "
                "fragments et un siècle figé qui n'aboutit qu'au Néant.",
    },
    {
        "id": "node-duviri", "parent_id": None,
        "label": "Duviri", "type": "era", "year": "Royaume paradoxal",
        "codex_slug": "duviri",
        "note": "Le drame du Drifter pris dans la Spirale infinie entre le "
                "Vide et la réalité, quête 'The Duviri Paradox' incluse.",
    },
    # ------------------------------ quêtes : Système d'Origine (chemin principal)
    {
        "id": "q-sacrifice", "parent_id": "era-origin",
        "label": "The Sacrifice", "type": "quest", "codex_slug": "the-sacrifice",
        "note": "Excalibur Umbra, Ballas et le dernier secret des Orokin. "
                "Découle de l'Octavia's Anthem.",
    },
    {
        "id": "q-octavia", "parent_id": "era-origin",
        "label": "Octavia's Anthem", "type": "quest", "codex_slug": "octavia-anthem",
        "note": "Le Mandachorde et l'Étoile chantée de Maprico. Suit la "
                "Guerre Intérieure, précède The Sacrifice.",
    },
    {
        "id": "q-vors", "parent_id": "era-origin",
        "label": "Vor's Prize", "type": "quest", "codex_slug": "vors-prize",
        "note": "Les Tenno renaissent : Lotus, Vor et la première entaille "
                "dans le Système.",
    },
    {
        "id": "q-second", "parent_id": "era-origin",
        "label": "The Second Dream", "type": "quest", "codex_slug": "second-dream",
        "note": "Le fœtus spectral : la vérité sur les Tenno, les Sentients "
                "et l'éveil de l'Opérateur.",
    },
    {
        "id": "q-within", "parent_id": "era-origin",
        "label": "The War Within", "type": "quest", "codex_slug": "war-within",
        "note": "Les Reines éternelles, la Kuva et l'héritage Orokin du "
                "Transférance.",
    },
    {
        "id": "q-harrow", "parent_id": "era-origin",
        "label": "Chains of Harrow", "type": "quest", "codex_slug": "chains-of-harrow",
        "note": "Rell, silence et les chaînes du Red Veil.",
    },
    {
        "id": "q-new-war", "parent_id": "era-origin",
        "label": "The New War", "type": "quest", "year": "Aboutissement",
        "codex_slug": "new-war",
        "note": "La guerre totale contre Ballas, les Sentients et le pacte "
                "du Drifter.",
    },
    {
        "id": "q-whispers", "parent_id": "era-origin",
        "label": "Whispers in the Walls", "type": "quest",
        "codex_slug": "whispers-in-the-walls",
        "note": "Albrecht Entrati, le Requiem et la cavité dans les "
                "fondations de la réalité.",
    },
    # ------------------------------ quêtes : Zariman (branche paradoxale)
    {
        "id": "q-zariman", "parent_id": "era-zariman",
        "label": "Angels of the Zariman", "type": "quest",
        "codex_slug": "angels-of-zariman",
        "note": "Le vaisseau-manifestation et le prix du voyage dans le Vide.",
    },
    {
        "id": "q-jade", "parent_id": "era-origin",
        "label": "Jade Shadows", "type": "quest", "codex_slug": "jade-shadows",
        "note": "Une lumière tombée du ciel et son enfant.",
    },
    {
        "id": "q-deimos", "parent_id": "era-origin",
        "label": "Heart of Deimos", "type": "quest", "codex_slug": "heart-of-deimos",
        "note": "Le cœur de l'Infestation, battant sous Deimos.",
    },
    # ------------------------------ quêtes : node-1999 (ère fusionnée)
    {
        "id": "q-hex", "parent_id": "node-1999",
        "label": "The Hex", "type": "quest", "codex_slug": "the-hex",
        "note": "Les six, la KIM et le lien qui défie les boucles.",
    },
    # ------------------------------ personnages
    {
        "id": "c-ballas", "parent_id": "era-orokin",
        "label": "Ballas", "type": "character", "codex_slug": "ballas",
        "note": "L'Exécuteur trahi : architecte des Sentients, juge des "
                "Tenno et, finalement, chrysalide de la Chute.",
    },
    {
        "id": "c-margulis", "parent_id": "era-orokin",
        "label": "Margulis", "type": "character", "codex_slug": "margulis",
        "note": "L'Enfant guide : elle a façonné les Tenno, chanté la "
                "Transférance et payé de sa vie leur protection.",
    },
    {
        "id": "c-lotus", "parent_id": "q-second",
        "label": "Lotus · Natah", "type": "character", "codex_slug": "lotus",
        "note": "Le visage de la guidance : Sentient au cœur partagé, cachée "
                "derrière le rêve de Margulis qu'elle a relevé.",
    },
    {
        "id": "c-teshin", "parent_id": "q-within",
        "label": "Teshin", "type": "character", "codex_slug": "teshin",
        "note": "Le Dax des derniers devoirs : gardien du Conclave et témoin "
                "silencieux de la Guerre Intérieure.",
    },
    {
        "id": "c-drifter", "parent_id": "q-new-war",
        "label": "Le Drifter", "type": "character", "codex_slug": "drifter",
        "note": "L'autre soi, arraché de la Zariman dans la Spirale de Duviri "
                "et ramené dans la guerre contre Ballas.",
    },
    {
        "id": "c-albrecht", "parent_id": "q-whispers",
        "label": "Albrecht Entrati", "type": "character",
        "codex_slug": "albrecht-entrati",
        "note": "L'archef dément : il a pillé la cavité de la réalité, "
                "falsifié l'éternisme et préparé la veille de 1999.",
    },
    # ------------------------------ lore des Warframes
    {
        "id": "wf-umbra", "parent_id": "q-sacrifice",
        "label": "Excalibur Umbra", "type": "warframe-lore",
        "codex_slug": "excalibur-umbra",
        "note": "Un Dax transpercé par le destrier : la première armure qui "
                "n'a jamais accepté sa boucle.",
    },
    {
        "id": "wf-inaros", "parent_id": "era-origin",
        "label": "Inaros", "type": "warframe-lore", "codex_slug": "inaros",
        "note": "Le seigneur des sables du Vide : sa dépouille veille encore "
                "sur le désert où il a englouti la défaite.",
    },
    {
        "id": "wf-gara", "parent_id": "era-origin",
        "label": "Gara", "type": "warframe-lore", "codex_slug": "gara",
        "note": "La glace levée contre le Loup : son éclat a scellé le "
                "mur de Cetus et demeure dans la veillée de Saya.",
    },
    # ------------------------------ fragments
    {"id": "f-sacrifice-excal", "parent_id": "q-sacrifice",
     "label": "Excalibur Umbra · Ballas", "type": "fragment"},
    {"id": "f-sacrifice-lotus", "parent_id": "q-sacrifice",
     "label": "Le Lotien survivant", "type": "fragment"},
    {"id": "f-octavia-maprico", "parent_id": "q-octavia",
     "label": "Mandachorde de Maprico", "type": "fragment"},
    {"id": "f-second-sentients", "parent_id": "q-second",
     "label": "Les Sentients · Céphalon", "type": "fragment"},
    {"id": "f-second-margulis", "parent_id": "q-second",
     "label": "Margulis · l'Enfant guide", "type": "fragment"},
    {"id": "f-within-queens", "parent_id": "q-within",
     "label": "Les Reines · la Kuva", "type": "fragment"},
    {"id": "f-within-teshin", "parent_id": "q-within",
     "label": "Teshin · le Dax", "type": "fragment"},
    {"id": "f-harrow-rell", "parent_id": "q-harrow",
     "label": "Rell · le Red Veil", "type": "fragment"},
    {"id": "f-whispers-requiem", "parent_id": "q-whispers",
     "label": "Requiem d'Albrecht", "type": "fragment"},
    {"id": "f-newwar-pact", "parent_id": "q-new-war",
     "label": "Pacte du Drifter", "type": "fragment"},
    {"id": "f-1999-hollvania", "parent_id": "node-1999",
     "label": "Höllvania · veille de 1999", "type": "fragment"},
    {"id": "f-1999-indifference", "parent_id": "node-1999",
     "label": "Le Néant approche", "type": "fragment"},
    {"id": "f-hex-kim", "parent_id": "q-hex",
     "label": "La KIM · les Liens", "type": "fragment"},
    {"id": "f-duviri-throne", "parent_id": "node-duviri",
     "label": "Le Trône du Drifter", "type": "fragment"},
    {"id": "f-duviri-thrax", "parent_id": "node-duviri",
     "label": "La Spirale de Duviri", "type": "fragment"},
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
