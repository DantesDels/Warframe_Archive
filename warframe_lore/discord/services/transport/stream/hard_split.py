"""Hard split on the generation-end marker emitted by the persona.

The LLM API ``stop`` parameter can silently fail (the model keeps generating
after the marker), so the Discord client performs its OWN truncation on this
exact string: the buffer is cut at the marker and the caller closes the stream.
Pure function, unit-testable without any Discord or WebSocket dependency.
"""

from __future__ import annotations

# Generation-end marker emitted by the persona (``*[Indexation terminée]*``).
STOP_MARKER = "[Indexation terminée]"


def apply_stop_marker(parts: list[str]) -> tuple[list[str] | None, bool]:
    """Truncate the accumulated token parts at the stop marker.

    Returns ``(truncated_parts, stopped)``:
      * ``None`` when the marker is absent (nothing to do);
      * content BEFORE the marker -> hard split, ``stopped`` is True and the
        caller must close the WebSocket (residual tokens are dropped);
      * marker at the very START of the reply -> persona RP decoration: it is
        stripped, ``stopped`` is False and the stream continues.
    """
    text = "".join(parts)
    if STOP_MARKER not in text:
        return None, False
    head, _, tail = text.partition(STOP_MARKER)
    if any(char.isalnum() for char in head):
        return [f"{head}\n\n{STOP_MARKER}"], True
    return [tail], False


__all__ = ["STOP_MARKER", "apply_stop_marker"]
