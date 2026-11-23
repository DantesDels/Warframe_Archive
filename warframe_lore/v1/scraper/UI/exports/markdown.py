"""Full merged Markdown corpora, never truncated to document excerpts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .pages import bucket_title, page_record, slug


def write_corpora(
    out_dir: Path,
    universe: dict[str, Any],
    docs: list[dict[str, Any]],
    generated_at: str,
) -> list[Path]:
    """Write the complete corpus and the canon-only corpus as Markdown."""
    name = slug(str(universe.get("name") or universe.get("id") or "Universe"))
    complete = out_dir / f"{name}_Complete.md"
    canon = out_dir / f"{name}_Canon.md"
    complete.write_text(_render(name, docs, generated_at, False), encoding="utf-8")
    canon.write_text(_render(name, docs, generated_at, True), encoding="utf-8")
    return [complete, canon]


def _render(
    name: str,
    docs: list[dict[str, Any]],
    generated_at: str,
    canon_only: bool,
) -> str:
    lines = [f"# {name}", "", f"_Generated: {generated_at}_", ""]
    groups: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        page = page_record(doc)
        if canon_only and page["canon_status"] != "canon":
            continue
        groups.setdefault(bucket_title(doc), []).append(page)
    for bucket, pages in sorted(groups.items()):
        lines.extend([f"## Bucket: {bucket}", ""])
        for page in pages:
            lines.extend([
                f"### {page['page_title']}",
                "",
                str(page["content_markdown"]),
                "",
                f"Source: {page['page_url']}",
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"
