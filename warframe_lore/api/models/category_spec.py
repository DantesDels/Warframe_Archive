"""Description d'un bucket logique de sortie."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CategorySpec:
    """Description d'un bucket logique de sortie.

    Attributes:
        id: identifiant unique du bucket (sert au suivi d'état).
        title: libellé humain (devient le champ ``category`` des entrées).
        filename: nom du megafile de sortie (ex: ``Lore_Quetes.json``).
        categories: noms de catégories réels de la source à résoudre.
        prefix: préfixes de titre à développer via ``list=allpages`` (source
            complémentaire aux catégories, utile quand le wiki ne catégorise
            pas toutes les pages, ex: ``Kinemantik Instant Messenger/``).
        title_include: ne garder que les titres contenant UN de ces sous-chaînes.
        title_exclude: exclure les titres contenant UN de ces sous-chaînes.
    """

    id: str
    title: str
    filename: str
    categories: list[str] = field(default_factory=list)
    prefix: list[str] = field(default_factory=list)
    title_include: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)