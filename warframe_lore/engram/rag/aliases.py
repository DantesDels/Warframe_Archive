"""Expansion de requête par alias (surnoms -> noms canoniques).

Certaines entrées ne sont connues du modèle d'embedding que sous leur nom
canonique (ex : « Lettie » -> page wiki « Leticia »).  ``resolve_alias``
enrichit la requête à embarquer (rappel), fournit une note d'alias injectée
dans le prompt (le modèle sait traduire le surnom) et un nom canonique pour
la désambiguïsation quand aucune donnée exacte n'est récupérée.
"""

from __future__ import annotations

# surnom (minuscules) -> (nom canonique, note mnémonique pour le prompt).
ALIASES = {
    "lettie": ("Leticia",
               "Lettie = Leticia Garcia, membre des Hex (1999)"),
}


def resolve_alias(question: str) -> tuple[str, str, str]:
    """Retourne (question enrichie, note d'alias, nom canonique).

    Sans correspondance, la question est retournée telle quelle et les deux
    autres valeurs sont vides.
    """
    low = question.lower()
    for alias, (canon, note) in ALIASES.items():
        if alias in low:
            # L'expansion lexicale force l'embedding à cibler les chunks du
            # nom canonique, là où le surnom seul serait ambigu.
            return f"{question} ({canon})", note, canon
    return question, "", ""