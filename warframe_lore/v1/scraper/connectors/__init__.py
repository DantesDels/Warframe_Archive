"""Outbound source connector adapters/ports (compat package)."""

from .registry import ConnectorRegistry, default_registry

__all__ = ["ConnectorRegistry", "default_registry"]
