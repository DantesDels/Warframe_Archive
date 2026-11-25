"""Declarative YAML/JSON text parser with zero domain hardcoding."""

from __future__ import annotations

import json
from typing import Any


def parse_config_text(text: str) -> dict[str, Any]:
    """Parse a JSON or YAML configuration string into a dictionary."""
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        return dict(json.loads(stripped))
    try:
        import yaml  # type: ignore[import-untyped]

        loaded = yaml.safe_load(stripped)
        return dict(loaded) if isinstance(loaded, dict) else {}
    except ImportError:
        return _parse_simple_yaml(stripped)


def _parse_scalar(raw: str) -> Any:
    val = raw.strip()
    if not val or val in ("null", "~", "None"):
        return None
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if val.lstrip("-").isdigit():
        return int(val)
    return val


def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    for idx, ch in enumerate(line):
        if ch in ('"', "'") and (idx == 0 or line[idx - 1] != "\\"):
            in_quote = None if in_quote == ch else (in_quote or ch)
        elif ch == "#" and in_quote is None:
            return line[:idx]
    return line


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = [
        (len(raw) - len(raw.lstrip(" ")), _strip_comment(raw).strip())
        for raw in text.splitlines()
    ]
    clean_lines = [(ind, content) for ind, content in lines if content]
    for idx, (indent, content) in enumerate(clean_lines):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            item_val = _parse_scalar(content[2:])
            if isinstance(parent, list):
                parent.append(item_val)
            continue
        key, _, rest = content.partition(":")
        k = key.strip().strip("\"'")
        v_str = rest.strip()
        if not v_str:
            next_is_list = (
                idx + 1 < len(clean_lines)
                and clean_lines[idx + 1][0] > indent
                and clean_lines[idx + 1][1].startswith("- ")
            )
            container: Any = [] if next_is_list else {}
            if isinstance(parent, dict):
                parent[k] = container
            stack.append((indent, container))
        elif isinstance(parent, dict):
            parent[k] = _parse_scalar(v_str)
    return root
