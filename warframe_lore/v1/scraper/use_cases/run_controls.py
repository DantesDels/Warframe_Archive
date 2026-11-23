"""Cooperative controls for universe execution."""

from __future__ import annotations

import threading


class RunControl:
    """Pause/cancel/checkpoint control shared with worker."""

    def __init__(self) -> None:
        self._pause = threading.Event()
        self._cancel = threading.Event()
        self._resume = threading.Event()
        self._resume.set()

    def pause(self) -> None:
        self._pause.set()
        self._resume.clear()

    def resume(self) -> None:
        self._pause.clear()
        self._resume.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()

    def is_paused(self) -> bool:
        return self._pause.is_set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def wait_if_paused(self, timeout: float = 0.2) -> bool:
        while self._pause.is_set() and not self._cancel.is_set():
            self._resume.wait(timeout=timeout)
        return not self._cancel.is_set()

    def checkpoint(self, path, payload) -> None:
        from ..storage import write_json

        write_json(path, payload)
