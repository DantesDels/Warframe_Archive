"""Storage mother folder: data models, persistence and produced datasets.

Sub-packages:
    * :mod:`warframe_lore.storage.db` -- PostgreSQL/pgvector models, the
      transactional manager and the RAG chunkers;
    * :mod:`warframe_lore.storage.output` -- JSON megafile models and writer
      (``out/*.json``, offline/NotebookLM consumption);
    * :mod:`warframe_lore.storage.timeline` -- curated lore chronology served
      by the local web UI.
"""
