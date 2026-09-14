#!/usr/bin/env python
"""Bootstrap PyInstaller pour l'exe ``cephalon-ui``.

Embarque l'interface web locale (``warframe_lore.ui.server``) dans un binaire
autonome ``--onefile``. Les fichiers statiques (static/) sont ajoutés via
``--add-data`` et repérés à l'exécution via ``sys._MEIPASS``.
"""

from warframe_lore.ui.server import main

if __name__ == "__main__":
    raise SystemExit(main())
