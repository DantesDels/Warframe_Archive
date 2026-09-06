"""Couche Sync : suivi de l'état delta (mode incrémental).

À terme, l'état est interrogé depuis la base SQL (``last_updated`` des
pages) plutôt que depuis un fichier JSON local.
"""

from .state import SyncState

__all__ = ["SyncState"]
