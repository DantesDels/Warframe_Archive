"""Main-thread snapshot of workspace data for background execution."""

from __future__ import annotations

from typing import Any


class Snapshot:
    """Detached copy of the data needed by one execution run."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.universes = {str(u["id"]): dict(u) for u in data.get("universes", [])}
        self.sources_by_uid = group(data.get("sources", []), "universeId")
        self.candidates_by_uid = group(data.get("candidates", []), "universeId")
        caps = data.get("capabilities", {})
        self.capabilities_by_uid = {
            str(key): dict(value) for key, value in caps.items()
        }

    def get(self, uid: str) -> dict[str, Any] | None:
        return self.universes.get(uid)


def snapshot(workspace: Any) -> Snapshot:
    return Snapshot(workspace.data)


def group(items: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        uid = str(item.get(key, ""))
        if uid:
            out.setdefault(uid, []).append(dict(item))
    return out
