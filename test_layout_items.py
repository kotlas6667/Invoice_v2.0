"""Regression: main form must be scrollable; Items columns stay aligned."""

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
class ScrollableMainTests(unittest.TestCase):
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
            self.app.destroy()
        except Exception:
            pass
        self._tmpdir.cleanup()

    def _settle(self, geometry: str) -> None:
        self.app.geometry(geometry)
        for _ in range(3):
            self.app.update()
            self.app.update_idletasks()

    def test_main_scroll_exists_and_contains_sections(self) -> None:
        self._settle("1100x640+10+10")
        self.assertTrue(hasattr(self.app, "main_scroll"))
        self.assertTrue(self.app.main_scroll.winfo_ismapped())
        self.assertTrue(self.app.items_card.winfo_ismapped())
        self.assertGreater(len(self.app.item_rows), 0)
        self.assertEqual(self.app.item_rows[0]["desc"].get(), "Garden services")

    def test_can_scroll_content_on_short_window(self) -> None:
        self._settle("1100x620+10+10")
        canvas = getattr(self.app.main_scroll, "_parent_canvas", None)
        self.assertIsNotNone(canvas)
        self.app.update_idletasks()
        bbox = canvas.bbox("all")
        self.assertIsNotNone(bbox)
        content_h = bbox[3] - bbox[1]
        view_h = canvas.winfo_height()
        self.assertGreater(content_h, view_h - 20)

    def test_qty_rate_amount_headers_align_with_fields(self) -> None:
        self._settle("1100x720+10+10")
        labels = self.app._items_header_labels
        row = self.app.item_rows[0]
        self.assertEqual(labels[2].cget("text"), "Qty")
        self.assertEqual(labels[3].cget("text"), "Rate")
        self.assertEqual(labels[4].cget("text"), "Amount")
        for i, key in ((2, "qty"), (3, "rate"), (4, "amount")):
            lx = labels[i].winfo_rootx()
            lw = labels[i].winfo_width()
            wx = row[key].winfo_rootx()
            ww = row[key].winfo_width()
            self.assertLessEqual(
                abs((lx + lw / 2) - (wx + ww / 2)),
                4,
                msg=f"{key} header/field center delta too large",
            )
            if key in ("qty", "rate"):
                self.assertEqual(row[key].cget("justify"), "center")
            else:
                self.assertIn(row[key].cget("anchor"), ("center", "c"))
