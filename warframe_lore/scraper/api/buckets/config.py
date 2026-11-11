"""Bucket configuration loading (``buckets.json``)."""

from __future__ import annotations

import json
import logging

from ..models import CategorySpec
from .defaults import DEFAULT_BUCKETS

log = logging.getLogger("warframe_lore.api.categories")


class BucketConfig:
    """Loads bucket definitions (from a file or the defaults)."""

    def __init__(self, specs: list[CategorySpec] | None = None) -> None:
        self.specs = specs if specs is not None else list(DEFAULT_BUCKETS)
        self._by_id = {b.id: b for b in self.specs}

    @classmethod
    def from_file(cls, path) -> BucketConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        specs = [CategorySpec(**raw) for raw in data.get("buckets", [])]
        return cls(specs)

    @classmethod
    def write_defaults(cls, path) -> None:
        payload = {"version": 1, "buckets": [
            {
                "id": b.id, "title": b.title, "filename": b.filename,
                "categories": b.categories,
                "prefix": b.prefix,
                "title_include": b.title_include,
                "title_exclude": b.title_exclude,
            } for b in DEFAULT_BUCKETS
        ]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        log.info("Default bucket configuration written -> %s", path)

    def get(self, bucket_id: str) -> CategorySpec:
        return self._by_id[bucket_id]

    def __iter__(self):
        return iter(self.specs)
