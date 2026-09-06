"""Modèles de données partagés du projet "Cephalon Archive".

Ces dataclasses sont *source-agnostics* : elles décrivent le contrat de
données entre les couches (API -> scraper -> cleaner -> output), quel que
soit le fournisseur (MediaWiki aujourd'hui, Reddit/Forums demain).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageData:
    """Contenu brut d'une page (avant tout nettoyage).

    ``content`` reste en format natif de la source (ex: Wikitext pour le
    wiki).  Le nettoyeur sait quel format traiter selon la source.
    """

    pageid: int
    title: str
    namespace: int
    touched: str | None = None
    last_revision_timestamp: str | None = None
    url: str = ""
    content: str = ""


@dataclass(frozen=True)
class TouchedInfo:
    """Information légère pour le calcul du delta (mode incrémental).

    C'est ce qui permet de ne re-télécharger que les pages modifiées sans
    avoir à récupérer leur contenu.
    """

    pageid: int | None
    title: str
    namespace: int = 0
    touched: str | None = None
    missing: bool = False


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
