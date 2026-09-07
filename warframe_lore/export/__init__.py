"""Warframe Public Export — ingestion des entités localisées du jeu.

Pipeline officiel (cf. wiki.warframe.com/w/Public_Export) :
  1. ``https://origin.warframe.com/PublicExport/index_<lang>.txt.lzma``  -> un
     flux LZMA **brut** contenant les noms hachés des manifests (1 par ligne,
     format ``Export<Category>_<lang>.json!00_<hash>``).
  2. Pour chaque nom haché, l'actif est servi par le serveur de contenu :
     ``http://content.warframe.com/PublicExport/Manifest/<nom_haché>``.
     L'actif est un JSON du type ``{"Export<Category>": [ {uniqueName, name,
     description, ...}, ... ]}``.

Le cache est **incrémental et sûr** : le hash ``!00_<hash>`` (content-addressed)
change uniquement quand le contenu change — un actif déjà téléchargé peut être
conservé indéfiniment et on re-synchronise en comparant les hashs de l'index.

Organisation du paquet :
    * ``const``    -> constantes (origines, langues, catégories retenues) ;
    * ``lzma``     -> décompression tolérante aux flux tronqués ;
    * ``assets``   -> validation d'actifs + normalisation des champs ;
    * ``extract``  -> extraction des entités localisées ;
    * ``fetch``    -> index + actifs hachés (cache incrémental) ;
    * ``sync``     -> boucle async de synchronisation en base ;
    * ``client``   -> :class:`PublicExportClient` (façade) ;
    * ``models``   -> :class:`GameEntity` (un fichier par classe).
"""

from __future__ import annotations

from .client import PublicExportClient
from .const import DEFAULT_LANGS, EXPORT_CATEGORIES
from .lzma import decompress_lzma
from .models import GameEntity

__all__ = [
    "DEFAULT_LANGS",
    "EXPORT_CATEGORIES",
    "GameEntity",
    "PublicExportClient",
    "decompress_lzma",
]