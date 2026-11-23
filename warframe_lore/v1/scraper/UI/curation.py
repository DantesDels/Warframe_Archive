"""Curation state operations layered over the base universe workspace."""

from __future__ import annotations

from typing import Any, cast

from ..discovery.models import Candidate
from ..slugs import slugify


class CurationMixin:
    """Candidate and source operations shared by the desktop workspace."""

    data: dict[str, Any]

    def save(self) -> None:
        for cls in type(self).__mro__:
            if cls is CurationMixin:
                continue
            if "save" in cls.__dict__:
                cast(Any, cls).save(self)
                return
        raise AttributeError("save")

    def _unique_id(self, base: str) -> str:
        for cls in type(self).__mro__:
            if cls is CurationMixin:
                continue
            if "_unique_id" in cls.__dict__:
                return str(cast(Any, cls)._unique_id(self, base))
        raise AttributeError("_unique_id")

    def set_candidates(self, candidates: list[Candidate]) -> None:
        self.data["candidates"] = [
            {
                "id": item.id,
                "universeId": item.universe_id,
                "kind": item.kind,
                "location": item.location,
                "title": item.title,
                "score": item.score,
                "proof": item.proof,
                "discoveredBy": item.discovered_by,
                "status": item.status,
                "forceUpdate": item.force_update,
            }
            for item in candidates
        ]
        self.save()

    def candidates_for(self, universe_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in cast(list[dict[str, Any]], self.data.get("candidates", []))
            if str(item.get("universeId")) == universe_id
        ]

    def update_candidate(self, candidate_id: str, **changes: Any) -> None:
        self._candidate(candidate_id).update(changes)
        self.save()

    def remove_candidate(self, candidate_id: str) -> None:
        self.data["candidates"] = [
            item
            for item in cast(list[dict[str, Any]], self.data.get("candidates", []))
            if str(item.get("id")) != candidate_id
        ]
        self.save()

    def add_source_from_candidate(self, candidate_id: str) -> dict[str, Any]:
        c = self._candidate(candidate_id)
        source: dict[str, Any] = {
            "id": self._unique_id(f"src-{c['id']}"),
            "universeId": c["universeId"],
            "kind": c["kind"],
            "location": c["location"],
            "status": "approved",
            "selected": True,
            "score": c["score"],
            "discoveredBy": c["discoveredBy"],
            "proof": c["proof"],
        }
        cast(list[dict[str, Any]], self.data.setdefault("sources", [])).append(source)
        self.update_candidate(candidate_id, status="active")
        self.save()
        return source

    def add_manual_source(
        self, universe_id: str, location: str, kind: str = "website"
    ) -> dict[str, Any]:
        base = slugify(location).replace("-", "")[:24] or "manuel"
        source: dict[str, Any] = {
            "id": self._unique_id(f"src-{base}"),
            "universeId": universe_id,
            "kind": kind,
            "location": location.strip(),
            "status": "approved",
            "selected": True,
            "score": 1.0,
            "discoveredBy": "manuel",
            "proof": "Ajout manuel depuis l'interface",
        }
        cast(list[dict[str, Any]], self.data.setdefault("sources", [])).append(source)
        self.save()
        return source

    def update_source(self, source_id: str, **changes: Any) -> dict[str, Any]:
        for item in cast(list[dict[str, Any]], self.data.get("sources", [])):
            if str(item.get("id")) == source_id:
                item.update(changes)
                self.save()
                return item
        raise KeyError(source_id)

    def delete_source(self, source_id: str) -> None:
        self.data["sources"] = [
            item
            for item in cast(list[dict[str, Any]], self.data.get("sources", []))
            if str(item.get("id")) != source_id
        ]
        self.data["documents"] = [
            item
            for item in cast(list[dict[str, Any]], self.data.get("documents", []))
            if str(item.get("sourceId")) != source_id
        ]
        self.save()

    def delete_universe(self, universe_id: str) -> None:
        for key in ("universes", "candidates"):
            self.data[key] = [
                item
                for item in cast(list[dict[str, Any]], self.data.get(key, []))
                if str(item.get("id")) != universe_id
            ]
        for key in ("sources", "documents"):
            self.data[key] = [
                item
                for item in cast(list[dict[str, Any]], self.data.get(key, []))
                if str(item.get("universeId")) != universe_id
            ]
        runs = cast(list[dict[str, Any]], self.data.get("runs", []))
        self.data["runs"] = [
            item
            for item in runs
            if universe_id not in cast(list[str], item.get("universeIds", []))
        ]
        self.save()

    def _candidate(self, candidate_id: str) -> dict[str, Any]:
        for item in cast(list[dict[str, Any]], self.data.get("candidates", [])):
            if str(item.get("id")) == candidate_id:
                return item
        raise KeyError(candidate_id)
