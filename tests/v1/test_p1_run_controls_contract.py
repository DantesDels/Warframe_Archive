"""P1 run control contracts: pause/cancel/resume/checkpoint."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.use_cases.run_controls import RunControl


class RunControlTests(unittest.TestCase):
    def test_pause_and_resume(self):
        ctl = RunControl()
        ctl.pause()
        resumed = {"ok": False}

        def waiter():
            ctl.wait_if_paused(timeout=0.05)
            resumed["ok"] = not ctl.is_paused()

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.1)
        self.assertFalse(resumed["ok"])
        ctl.resume()
        t.join(timeout=1)
        self.assertTrue(resumed["ok"])

    def test_cancel_unblocks_pause(self):
        ctl = RunControl()
        ctl.pause()
        result = {"ok": True}

        def waiter():
            result["ok"] = ctl.wait_if_paused(timeout=0.05)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.1)
        ctl.cancel()
        t.join(timeout=1)
        self.assertFalse(result["ok"])
        self.assertTrue(ctl.is_cancelled())

    def test_checkpoint_writes_file(self):
        ctl = RunControl()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            ctl.checkpoint(path, {"universe_id": "u1", "last_source_index": 2})
            self.assertTrue(path.exists())
            self.assertIn("u1", path.read_text(encoding="utf-8"))
