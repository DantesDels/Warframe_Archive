"""Pure domain transformations: JSON collection filtering and dict_lookup."""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import CollectionFilterConfig, DictLookupRuleConfig

_DEFAULT_LOGGER = logging.getLogger(__name__)


def extract_collection_items(data: Any) -> list[Any]:
    """Return the root collection items from a JSON list or dict payload."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return value
        return list(data.values())
    return []


def matches_collection_filter(
    data: Any, rule: CollectionFilterConfig
) -> tuple[bool, str]:
    """Validate a parsed JSON document against generic collection filter rules."""
    items = extract_collection_items(data)
    count = len(items)
    if rule.min_items > 0 and count < rule.min_items:
        return False, f"min_items({count}<{rule.min_items})"
    if rule.max_items is not None and count > rule.max_items:
        return False, f"max_items({count}>{rule.max_items})"
    if rule.required_keys and isinstance(data, dict):
        missing = [k for k in rule.required_keys if k not in data]
        if missing:
            return False, f"missing_keys({','.join(missing)})"
    return True, ""


def _matches_lookup_trigger(value: str, rule: DictLookupRuleConfig, pat: Any) -> bool:
    if rule.prefix and value.startswith(rule.prefix):
        return True
    if pat is not None and pat.search(value):
        return True
    return bool(not rule.prefix and pat is None and value)


def _inject_target(
    obj: dict[str, Any], target_field: str, resolved_map: dict[str, str | None]
) -> None:
    parts = [p for p in target_field.split(".") if p]
    if not parts:
        return
    cur = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    leaf = parts[-1]
    existing = cur.get(leaf)
    if isinstance(existing, dict):
        existing.update(resolved_map)
    else:
        cur[leaf] = dict(resolved_map)


def apply_dict_lookup(
    data: Any,
    rule: DictLookupRuleConfig | None,
    dictionaries: dict[str, dict[str, str]],
    *,
    logger: Any = None,
) -> tuple[Any, int, list[str]]:
    """Recursively resolve matching fields across external dictionaries."""
    if rule is None or not dictionaries:
        return data, 0, []
    log = logger or _DEFAULT_LOGGER
    compiled = re.compile(rule.regex) if rule.regex else None
    resolved_count = 0
    missing_keys: list[str] = []

    def _walk(node: Any) -> Any:
        nonlocal resolved_count
        if isinstance(node, list):
            return [_walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {k: _walk(v) for k, v in node.items()}
        raw_val = out.get(rule.source_field)
        if isinstance(raw_val, str) and _matches_lookup_trigger(
            raw_val, rule, compiled
        ):
            resolved_by_lang: dict[str, str | None] = {}
            for lang, mapping in dictionaries.items():
                if raw_val in mapping:
                    resolved_by_lang[lang] = str(mapping[raw_val])
                    resolved_count += 1
                else:
                    resolved_by_lang[lang] = None
                    missing_tag = f"{lang}:{raw_val}"
                    missing_keys.append(missing_tag)
                    log.warning(
                        "Missing dictionary key '%s' in '%s'", raw_val, lang
                    )
            _inject_target(out, rule.target_field, resolved_by_lang)
        return out

    transformed = _walk(data)
    return transformed, resolved_count, missing_keys
