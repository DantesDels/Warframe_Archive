"""Interface abstraite pour toutes les sources de données.

Le projet est construit pour être extensible : aujourd'hui nous ne
consommons que le wiki MediaWiki (``MediaWikiSource``), mais demain il sera
possible de brancher Reddit, les Forums officiels, etc.  C'est cette
interface qui rend cette évolution possible sans toucher au reste du
pipeline (scraper, cleaner, output).

Chaque nouvelle source doit :
  * hériter de :class:`BaseSource` ;
  * implémenter les trois méthodes abstraites (fetch_pages, check_updates,
    resolve_categories) ;
  * rester un composant de communication PURE (aucun nettoyage ici).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import CategorySpec, PageData, TouchedInfo

__all__ = ["BaseSource", "CategorySpec", "PageData", "TouchedInfo"]


class BaseSource(ABC):
    """Interface commune à toutes les sources de données.

    Le pipeline (``scraper.py``) dépend uniquement de cette interface.  Cela
    respecte le principe SOLID *Dependency Inversion* : le code de haut
    niveau ne dépend pas d'implémentations concrètes.
    """

    name: str = "base"

    @abstractmethod
    def fetch_pages(self, titles: list[str]) -> dict[str, PageData]:
        """Récupère le contenu complet des pages demandées.

        Returns:
            Mapping ``titre -> PageData`` (seules les pages trouvées).
        """

    @abstractmethod
    def check_updates(self, titles: list[str]) -> dict[str, TouchedInfo]:
        """Récupère uniquement les métadonnées de modification (champ ``touched``).

        Utilisé pour le mode delta : on compare avec l'état local pour
        décider quelles pages re-télécharger.
        """

    @abstractmethod
    def resolve_categories(
        self,
        category_names: list[str],
    ) -> dict[str, set[str]]:
        """Résout des catégories en listes de titres de pages.

        Args:
            category_names: noms de catégories à développer.

        Returns:
            Mapping ``nom_catégorie -> set de titres de pages`` (sous-catégories
            incluses selon la source).
        """

    def resolve_prefix(self, prefix: str) -> set[str]:
        """Titres (ns=0) commençant par ``prefix`` (découverte par préfixe).

        Méthode non-abstraite : les sources qui ne supportent pas la
        découverte par préfixe retournent simplement un ensemble vide.
        Celles qui la supportent (ex: MediaWiki ``list=allpages``) la
        surchargent.
        """
        return set()
