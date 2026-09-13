"""``cephalon ui`` interface: local web server + frontend.

Browse the scraped lore (megafiles ``out/*.json``): buckets, pages, KIM
dialogues, recent pages and full-text search. The frontend (``static/``) is
served by a minimal stdlib HTTP server.

Related commands:
    * ``cephalon ui``        -> starts the interface (server + browser).
    * ``cephalon-ui``        -> standalone entry point (PyInstaller exe).
"""

from .server import LoreStore, launch, main, serve_forever

__all__ = ["LoreStore", "launch", "serve_forever", "main"]
