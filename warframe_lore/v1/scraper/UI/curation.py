"""Curation state operations layered over the base universe workspace."""

from __future__ import annotations

from ..discovery.models import Candidate
from ..slugs import slugify


class CurationMixin:
    """Candidate and source operations shared by the desktop workspace."""

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

    def candidates_for(self, universe_id: str) -> list[dict]:
        return [
            item
            for item in self.data["candidates"]
            if item["universeId"] == universe_id
        ]

    def update_candidate(self, candidate_id: str, **changes) -> None:
        self._candidate(candidate_id).update(changes)
        self.save()

    def remove_candidate(self, candidate_id: str) -> None:
        self.data["candidates"] = [
            item for item in self.data["candidates"] if item["id"] != candidate_id
        ]
        self.save()

    def add_source_from_candidate(self, candidate_id: str) -> dict:
        candidate = self._candidate(candidate_id)
        source = {
            "id": self._unique_id(f"src-{candidate['id']}"),
            "universeId": candidate["universeId"],
            "kind": candidate["kind"],
            "location": candidate["location"],
            "status": "approved",
            "selected": True,
            "score": candidate["score"],
            "discoveredBy": candidate["discoveredBy"],
            "proof": candidate["proof"],
        }
        self.data["sources"].append(source)
        self.update_candidate(candidate_id, status="active")
        self.save()
        return source

    def add_manual_source(
        self,
        universe_id: str,
        location: str,
        kind: str = "website",
    ) -> dict:
        base = slugify(location).replace("-", "")[:24] or "manuel"
        source = {
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
        self.data["sources"].append(source)
        self.save()
        return source

    def update_source(self, source_id: str, **changes) -> dict:
        for item in self.data["sources"]:
            if item["id"] == source_id:
                item.update(changes)
                self.save()
                return item
        raise KeyError(source_id)

    def delete_source(self, source_id: str) -> None:
        self.data["sources"] = [
            item for item in self.data["sources"] if item["id"] != source_id
        ]
        self.data["documents"] = [
            item for item in self.data["documents"] if item["sourceId"] != source_id
        ]
        self.save()

    def delete_universe(self, universe_id: str) -> None:
        for key in ("universes", "candidates"):
            self.data[key] = [
                item for item in self.data[key] if item["id"] != universe_id
            ]
        for key in ("sources", "documents"):
            self.data[key] = [
                item for item in self.data[key] if item["universeId"] != universe_id
            ]
        self.data["runs"] = [
            item for item in self.data["runs"] if universe_id not in item["universeIds"]
        ]
        self.save()

    def _candidate(self, candidate_id: str) -> dict:
        for item in self.data["candidates"]:
            if item["id"] == candidate_id:
                return item
        raise KeyError(candidate_id)
