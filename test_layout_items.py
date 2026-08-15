"""Regression: Items box must stay visible on short / scaled screens."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith("linux"), "Xvfb layout check is Linux-only")
class ItemsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DISPLAY"] = ":99"
        subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1920x1080x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.4)

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        import config

        config.DB_PATH = Path(self._tmpdir.name) / "InvoiceDb.db"
        config.FROM_SETTINGS_PATH = Path(self._tmpdir.name) / "from.json"
        import database

        importlib.reload(database)

        import tkinter.messagebox as mb

        mb.showinfo = lambda *a, **k: True
        mb.showwarning = lambda *a, **k: True
        mb.showerror = lambda *a, **k: True
        mb.askyesno = lambda *a, **k: True

        for name in ("invoice", "invoice_list"):
            sys.modules.pop(name, None)
        from invoice import InvoiceApp

        self.app = InvoiceApp()

    def tearDown(self) -> None:
        try:
            if getattr(self.app, "_layout_after_id", None) is not None:
                try:
                    self.app.after_cancel(self.app._layout_after_id)
                except Exception:
                    pass
            self.app.unbind("<Configure>")
            self.app.destroy()
        except Exception:
            pass
        self._tmpdir.cleanup()

    def _settle(self, geometry: str) -> None:
        self.app.geometry(geometry)
        for _ in range(3):
            self.app.update()
            self.app.update_idletasks()
            self.app._apply_responsive_layout()
            self.app.update()

    def test_items_visible_at_1080p_150_percent_logical_height(self) -> None:
        # 1920x1080 @ 150% ≈ 1280x720 logical workspace.
        self._settle("1100x720+10+10")
        card = self.app.items_card
        kids = card.winfo_children()
        self.assertGreaterEqual(card.winfo_height(), 200)
        self.assertGreaterEqual(kids[1].winfo_height(), 20)  # column headers
        self.assertGreaterEqual(kids[2].winfo_height(), 80)  # rows viewport
        self.assertGreater(self.app.item_rows[0]["frame"].winfo_height(), 0)
        self.assertLess(
            card.winfo_rooty() + 50,
            self.app.winfo_rooty() + self.app.winfo_height(),
        )

    def test_items_visible_on_tighter_window(self) -> None:
        self._settle("1100x640+10+10")
        card = self.app.items_card
        kids = card.winfo_children()
        self.assertGreaterEqual(card.winfo_height(), 200)
        self.assertGreaterEqual(kids[2].winfo_height(), 80)
        self.assertLessEqual(self.app.top_container.winfo_height(), 360)


if __name__ == "__main__":
    unittest.main()
