"""Sync layer: delta state tracking (incremental mode).

Eventually the state will be queried from the SQL database (``last_updated``
of pages) rather than from a local JSON file.
"""

from .state import SyncState

__all__ = ["SyncState"]
