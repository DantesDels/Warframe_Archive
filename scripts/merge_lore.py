"""Prepare the Warframe lore corpus for an online LLM or NotebookLM.

Two output modes:

* **single file** (default) -- one merged Markdown document. Handy for a
  model with a huge context window, but it exceeds the limits of most
  single-prompt / single-source tools (see the size warnings).

* **per-bucket** (``--per-bucket``) -- one Markdown file per megafile bucket,
  written into ``--out-dir``.  This is the recommended mode for
  **NotebookLM**: each file becomes one source, kept under the per-source
  limits (~500 k words / 25 MB) by splitting oversized buckets into
  numbered parts, and the resulting set fits inside NotebookLM's
  50-sources-per-notebook cap.  An ``INDEX.md`` is also written, listing
  every source with its page count and size.

Usage:
    # One merged file (large)
    python scripts/merge_lore.py [--out PATH] [--lang en|fr|all]
                                [--canon-only] [--buckets ID1,ID2]
                                [--max-pages N]

    # NotebookLM-friendly: one file per bucket (split when too large)
    python scripts/merge_lore.py --per-bucket [--out-dir DIR] [--lang en|fr|all]
                                 [--canon-only] [--buckets ID1,ID2]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

# NotebookLM per-source soft limits (warn well before the hard cap).
NB_MAX_WORDS = 500_000
NB_WARN_WORDS = 400_000


def is_french(path: Path) -> bool:
    return "_FR" in path.stem


def slugify(name: str) -> str:
    return name.replace(" ", "_").replace("/", "-")


def selected_megas(args: argparse.Namespace) -> list[Path]:
    megas = []
    for mega in sorted(OUT_DIR.glob("Lore_*.json")):
        if args.lang == "en" and is_french(mega):
            continue
        if args.lang == "fr" and not is_french(mega):
            continue
        if args.buckets:
            stem = mega.stem
            alt = mega.stem.replace("Lore_", "")
            if stem not in args.buckets and alt not in args.buckets:
                continue
        megas.append(mega)
    return megas


def filter_pages(mega: Path, args: argparse.Namespace) -> tuple[str, list[dict]]:
    data = json.loads(mega.read_text(encoding="utf-8"))
    meta = data.get("metadata") or {}
    bucket_title = meta.get("bucket_title", mega.stem)
    pages = []
    for page in data.get("pages", []):
        if args.canon_only and page.get("canon_status") != "canon":
            continue
        pages.append(page)
        if args.max_pages and len(pages) >= args.max_pages:
            break
    return bucket_title, pages


def render_page(page: dict) -> str:
    title = page.get("page_title", "Untitled")
    status = page.get("canon_status", "unknown")
    category = page.get("category", "")
    header = f"### {title}"
    if category:
        header += f"  _(category: {category})_"
    content = (page.get("content_markdown") or "").strip()
    parts = [header, f"_canon_status: {status}_", ""]
    if content:
        parts.append(content)
    parts.append("")
    parts.append("---")
    parts.append("")
    return "\n".join(parts)


def render_bucket(bucket_title: str, pages: list[dict], mega: Path) -> str:
    lines = [
        f"# Warframe Lore — {bucket_title}",
        "",
        f"> Source: Cephalon Archive (`out/{mega.name}`)",
        f"> Pages: {len(pages)}",
        "",
    ]
    for page in pages:
        lines.append(render_page(page))
    return "\n".join(lines)


def word_count(text: str) -> int:
    return len(text.split())


def split_pages_into_parts(pages: list[dict], max_words: int) -> list[list[dict]]:
    """Split a page list into chunks whose rendered word count stays under
    ``max_words``, cutting only on page boundaries."""
    parts: list[list[dict]] = []
    current: list[dict] = []
    current_words = 0
    for page in pages:
        page_words = word_count(render_page(page))
        if current and current_words + page_words > max_words:
            parts.append(current)
            current = []
            current_words = 0
        current.append(page)
        current_words += page_words
    if current:
        parts.append(current)
    return parts or [[]]


def run_single(args: argparse.Namespace) -> int:
    pages_out: list[tuple[str, dict]] = []
    for mega in selected_megas(args):
        bucket_title, pages = filter_pages(mega, args)
        for page in pages:
            pages_out.append((bucket_title, page))
            if args.max_pages and len(pages_out) >= args.max_pages:
                break
        if args.max_pages and len(pages_out) >= args.max_pages:
            break

    lines = [
        "# Warframe Lore — Complete Corpus",
        "",
        "> Merged from the Cephalon Archive megafiles (`out/Lore_*.json`).",
        "> Each section is one wiki page; `canon_status` is preserved.",
        "",
    ]
    current_bucket = None
    for bucket_title, page in pages_out:
        if bucket_title != current_bucket:
            current_bucket = bucket_title
            lines.append(f"\n## Bucket: {bucket_title}\n")
        lines.append(render_page(page).rstrip())
        lines.append("")
    text = "\n".join(lines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print_stats(args.out, text, len(pages_out))
    return 0


def run_per_bucket(args: argparse.Namespace) -> int:
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clean stale outputs from a previous run.
    for old in out_dir.glob("Warframe_Lore_*.md"):
        old.unlink()
    manifest: list[tuple[str, Path, int, int]] = []
    total_pages = 0
    for mega in selected_megas(args):
        bucket_title, pages = filter_pages(mega, args)
        if not pages:
            continue
        # Split oversized buckets so every source stays under NotebookLM's
        # per-source word cap.
        parts = split_pages_into_parts(pages, NB_WARN_WORDS)
        multi = len(parts) > 1
        for idx, part in enumerate(parts, 1):
            text = render_bucket(bucket_title, part, mega)
            if multi:
                fname = f"Warframe_Lore_{slugify(bucket_title)}_part{idx}.md"
            else:
                fname = f"Warframe_Lore_{slugify(bucket_title)}.md"
            path = out_dir / fname
            path.write_text(text, encoding="utf-8")
            wc = word_count(text)
            if multi:
                label = f"{bucket_title} (part {idx}/{len(parts)})"
            else:
                label = bucket_title
            manifest.append((label, path, len(part), wc))
            total_pages += len(part)
            flag = "  [LARGE]" if wc > NB_WARN_WORDS else ""
            print(f"  {fname:55s} pages={len(part):5d} words={wc:7,d}{flag}")

    # Write an index file so NotebookLM users know what each source contains.
    index_lines = [
        "# Warframe Lore — NotebookLM Source Index",
        "",
        f"Generated from the Cephalon Archive. {len(manifest)} sources, "
        f"{total_pages} pages total.",
        "",
        "| # | Source file | Bucket | Pages | Words |",
        "|---|---|---|---:|---:|",
    ]
    for i, (title, path, pages, wc) in enumerate(manifest, 1):
        index_lines.append(f"| {i} | `{path.name}` | {title} | {pages} | {wc:,} |")
    index_lines.append("")
    index_lines.append("## Notes")
    index_lines.append("")
    index_lines.append("- Each `.md` file is one NotebookLM source.")
    index_lines.append("- Import all of them into a single notebook (<= 50 sources).")
    index_lines.append("- `canon_status` is preserved per page (`canon` / "
                       "`speculation` / `community_theory`).")
    index_lines.append("- Regenerate after `cephalon run` to refresh the corpus.")
    (out_dir / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")
    print(f"\nWrote {len(manifest)} sources + INDEX.md to {out_dir}")
    print(f"  total pages: {total_pages}")
    if len(manifest) > 50:
        print("  WARNING: more than 50 sources - NotebookLM's per-notebook cap.")
    oversized = [m for m in manifest if m[3] > NB_MAX_WORDS]
    if oversized:
        print("  WARNING: sources above NotebookLM's ~500k-word per-source cap:")
        for _, p, _, w in oversized:
            print(f"    {p.name} ({w:,} words)")
    return 0


def print_stats(path: Path, text: str, pages: int) -> None:
    chars = len(text)
    tokens = chars // 4
    words = word_count(text)
    print(f"Wrote {path}")
    print(f"  pages : {pages}")
    print(f"  chars : {chars:,}")
    print(f"  words : {words:,}")
    print(f"  ~tokens: {tokens:,} (estimate, 4 chars/token)")
    if words > NB_WARN_WORDS:
        print("  WARNING: very large - most single-prompt / single-source tools "
              "cannot ingest this in one go. Consider --per-bucket, --canon-only, "
              "or --buckets.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--out", type=Path, default=OUT_DIR / "Warframe_Lore_Complete.md",
        help="Output file (single-file mode).")
    parser.add_argument(
        "--out-dir", type=Path, default=OUT_DIR / "notebooklm",
        help="Output directory (per-bucket mode).")
    parser.add_argument("--lang", choices=("en", "fr", "all"), default="en")
    parser.add_argument("--canon-only", action="store_true")
    parser.add_argument("--buckets", help="Comma-separated bucket ids/stems to keep.")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--per-bucket", action="store_true",
        help="Write one Markdown file per bucket (NotebookLM-friendly).")
    args = parser.parse_args()
    if args.buckets:
        args.buckets = [b.strip() for b in args.buckets.split(",")]
    else:
        args.buckets = None

    if args.per_bucket:
        return run_per_bucket(args)
    return run_single(args)


if __name__ == "__main__":
    raise SystemExit(main())
