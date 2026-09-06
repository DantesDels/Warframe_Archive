"""Interface ``cephalon ui`` : serveur web local + frontend.

Permet de naviguer dans le lore récupéré (megafiles ``out/*.json``) :
buckets, pages, dialogues KIM, pages récentes et recherche plein texte.
Le frontend (``static/``) est servi par un mini serveur HTTP stdlib.

Commandes associées :
    * ``cephalon ui``     -> lance l'interface (serveur + navigateur).
    * ``cephalon-ui``     -> entry point autonome (exe PyInstaller).
"""

from .server import LoreStore, main, serve_forever

__all__ = ["LoreStore", "serve_forever", "main"]