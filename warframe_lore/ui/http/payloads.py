"""JSON payloads of the lore and KIM routes, built from ``LoreStore``.

Single responsibility: turn a parsed query string into the payload the frontend
expects — the pages of a bucket, one page (footer noise cut and patch notes
extracted on the fly), and the KIM views (character list, conversation list, one
conversation).  Pure functions over the store: no HTTP object here, so every
payload is testable without a server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

from ...cleaner.formatting import cut_footer_noise, normalise_deep_headings
from ..patch_notes import _PATCH_HISTORY_HEADING, extract_patch_notes

if TYPE_CHECKING:
    from ..data.store import LoreStore

EMPTY_KIM = {"character": None, "spoiler": None, "conversations": []}
EMPTY_CONVERSATION = {"id": None, "title": None, "rank": None, "messages": []}


def _first(query: dict, key: str) -> str:
    """First raw value of a query parameter ("" when absent)."""
    return (query.get(key) or [""])[0]


def pages_for_query(store: LoreStore, query: dict) -> list[dict]:
    """Pages of the requested bucket (empty when the bucket is unknown)."""
    bucket = _first(query, "bucket")
    if not bucket or not store.bucket_exists(bucket):
        return []
    return store.list_pages(bucket)


def page_for_query(store: LoreStore, query: dict) -> dict | None:
    """One page, with the footer noise cut and the patch notes extracted."""
    bucket = _first(query, "bucket")
    title = unquote(_first(query, "title"))
    if bucket and not store.bucket_exists(bucket):
        return None
    page = (store.get_page(bucket, title) if store.bucket_exists(bucket)
            else store.get_dialogue_page(title))
    if page is None:
        return None
    result = dict(page)
    # Relais du filtre footer du scraper : les megafiles servis n'ont pas été
    # regénérés depuis l'ajout de ``cut_footer_noise`` — la même troncature est
    # appliquée à la volée (navboxes / catégories / historique ``Update``) AVANT
    # l'extraction des patch notes, pour ne pas créer de versions fantômes à
    # partir des lignes de footer (``Update 37``, ``Hildryn``…).
    content = cut_footer_noise(
        normalise_deep_headings(result.get("content_markdown", "")))
    if _PATCH_HISTORY_HEADING.search(content):
        patches, rest = extract_patch_notes(content)
        result["patch_notes"] = patches
        result["content_markdown"] = rest
    else:
        result["content_markdown"] = content
    return result


def kim_for_query(store: LoreStore, query: dict) -> list[dict] | dict:
    """KIM view: character list, one character, or one conversation."""
    title = unquote(_first(query, "title"))
    if not title:
        return store.kim_pages()
    page = store.get_dialogue_page(title)
    content = (page or {}).get("content_markdown", "")
    if not page or not store._looks_like_dialogue(content):
        return dict(EMPTY_KIM)
    conversation = unquote(_first(query, "conv"))
    if not conversation:
        return _kim_character(store, title, content)
    return _kim_conversation(store, title, content, conversation,
                             _first(query, "mode"))


def _kim_character(store: LoreStore, title: str, content: str) -> dict:
    """One KIM character: spoiler warning + conversation summaries."""
    return {
        "character": title.rsplit("/", 1)[-1],
        "spoiler": store.spoiler_warning(content),
        "conversations": [
            {"id": item["id"], "title": item["title"], "rank": item["rank"],
             "source": item.get("source", "wiki")}
            for item in store.kim_conversations(title)
        ],
    }


def _kim_conversation(store: LoreStore, title: str, content: str,
                      conversation: str, mode: str) -> dict:
    """One conversation: datamine detail when available, wiki body otherwise."""
    for item in store.kim_conversations(title):
        if item["id"] != conversation:
            continue
        result = {"id": item["id"], "title": item["title"], "rank": item["rank"]}
        character = title.rsplit("/", 1)[-1].strip()
        detail = store.kim_dm.conversation(character, conversation)
        if mode == "sim":
            result["script"] = (detail["script"] if detail is not None
                                else store._build_kim_script(item["body"]))
            result["spoiler"] = store.spoiler_warning(content)
        else:
            result["messages"] = (detail["messages"] if detail is not None
                                  else store._parse_dialogue(item["body"]))
            result["source"] = detail["source"] if detail else "wiki"
        return result
    return dict(EMPTY_CONVERSATION)


__all__ = ["kim_for_query", "page_for_query", "pages_for_query"]
