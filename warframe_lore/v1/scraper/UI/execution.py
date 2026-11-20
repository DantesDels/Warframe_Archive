"""Non-blocking execution panel with progress and live log stream."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk


class ExecutionPanel(ttk.LabelFrame):
    """Bottom panel showing progress and streaming execution logs."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text="Exécution", padding=(8, 6))
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._progress = tk.IntVar(value=0)
        self._status = tk.StringVar(value="En attente — aucune exécution en cours.")
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, textvariable=self._status).pack(side="left")
        ttk.Progressbar(
            self, maximum=100, variable=self._progress, mode="determinate",
        ).pack(fill="x", pady=(4, 6))
        self._log = tk.Text(self, height=7, wrap="word", state="disabled")
        self._log.pack(fill="both", expand=True)
        self.after(120, self._drain)

    def clear(self) -> None:
        self._progress.set(0)
        self._status.set("En attente — aucune exécution en cours.")
        self._write("", replace=True)

    def append_log(self, line: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._write(f"[{stamp}] {line}\n")

    def run(self, plan) -> None:
        """Start a simulated non-blocking execution for the given plan."""
        self.clear()
        self.append_log("Préparation du plan d'exécution validé.")
        thread = threading.Thread(target=self._worker, args=(plan,), daemon=True)
        thread.start()

    def _worker(self, plan) -> None:
        steps = [
            ("Découverte et filtrage", 15),
            ("Validation sécurité des sources", 35),
            ("Récupération et tri", 60),
            ("Génération des formats", 85),
            ("Préparation RAG", 100),
        ]
        for label, percent in steps:
            time.sleep(0.35)
            self._queue.put(("progress", percent, label))
            self._queue.put(("log", f"Étape : {label} — {percent} %"))
        formats = ", ".join(f.upper() for f in plan.settings.output_formats)
        rag = "activé" if plan.settings.rag_coupling else "désactivé"
        self._queue.put(("log", f"Formats : {formats} | Couplage RAG : {rag}"))
        self._queue.put(("log", "Exécution simulée terminée (moteur S4 à brancher)."))
        self._queue.put(("progress", 100, "Terminé"))

    def _drain(self) -> None:
        try:
            while True:
                event = self._queue.get_nowait()
                if event[0] == "progress":
                    _, percent, label = event
                    self._progress.set(percent)
                    self._status.set(f"{percent} % — {label}")
                elif event[0] == "log":
                    self.append_log(event[1])
        except queue.Empty:
            pass
        self.after(120, self._drain)

    def _write(self, text: str, replace: bool = False) -> None:
        self._log.configure(state="normal")
        if replace:
            self._log.delete("1.0", "end")
        if text:
            self._log.insert("end", text)
            self._log.see("end")
        self._log.configure(state="disabled")
