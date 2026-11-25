"""Minimal YAML frontmatter rendering and parsing for vault notes.

Only the controlled note schema is handled (scalars, booleans, integers
and inline string lists), keeping the synthesizer dependency-free.
"""

from __future__ import annotations

import re
from typing import Any

_LIST_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        items = ", ".join('"' + str(item).replace('"', '\\"') + '"' for item in value)
        return f"[{items}]"
    return '"' + str(value).replace('"', '\\"') + '"'


def render_frontmatter(fields: dict[str, Any]) -> str:
    """Serialize note metadata as a YAML frontmatter block."""
    lines = ["---"]
    lines.extend(f"{key}: {_render_value(value)}" for key, value in fields.items())
    lines.append("---")
    return "\n".join(lines)


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [m.group(1).replace('\\"', '"') for m in _LIST_ITEM_RE.finditer(value)]
    if value in ("true", "false"):
        return value == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a note into its frontmatter mapping and Markdown body."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            fields: dict[str, Any] = {}
            for line in lines[1:index]:
                key, sep, raw = line.partition(":")
                if sep and key.strip():
                    fields[key.strip()] = _parse_value(raw)
            return fields, "".join(lines[index + 1 :])
    return {}, text
