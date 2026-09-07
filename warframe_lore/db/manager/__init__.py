"""Gestionnaire de base de données SQL — composition des mixins.

``SQLDatabaseManager`` remplace la logique purement JSON pour la persistance
relationnelle : il écrit les pages nettoyées dans PostgreSQL (upsert
transactionnel), en parallèle des megafiles JSON.

La classe est composée par héritage multiple depuis les mixins ciblés :
    * ``base``      — cycle de vie (engine, session, DDL) ;
    * ``ingest``    — upsert page + chunks + dialogues ;
    * ``entities``  — entités localisées du jeu ;
    * ``delta``     — suivi du mode delta (``sync_state``) ;
    * ``queries``   — diagnostics (stats, pages récentes).
"""

from __future__ import annotations

from .base import SQLSessionBase
from .delta import SQLDeltaMixin
from .entities import SQLEntitiesMixin
from .ingest import SQLIngestMixin
from .queries import SQLQueryMixin

__all__ = ["SQLDatabaseManager"]


class SQLDatabaseManager(SQLSessionBase, SQLIngestMixin, SQLEntitiesMixin,
                         SQLDeltaMixin, SQLQueryMixin):
    """Point d'entrée public de la couche SQL (voir les mixins)."""