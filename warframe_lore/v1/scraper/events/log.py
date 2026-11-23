"""Outbound event log adapter (compat)."""

from ..adapters.outbound.persistence.event_log import JsonlEventLogAdapter as EventLog

__all__ = ["EventLog"]
