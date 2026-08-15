"""Regression tests for invoice write/update path."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path


class InvoiceSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "InvoiceDb.db"

        import config

        config.DB_PATH = db_path
        import database as db

        self.db = importlib.reload(db)
        self.db.init_db()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _client(self, **overrides) -> "db.Client":
        data = dict(
            id=None,
            name="Jane",
            surname="Doe",
            company="Acme",
            address="Old Street",
            city="London",
            zip="E1",
            country="England",
        )
        data.update(overrides)
        return self.db.Client(**data)

    def _item(self, desc: str = "Work", qty: int = 2, rate: float = 10.0):
        return self.db.InvoiceItem(desc, qty, rate, qty * rate, 0.0)

    def test_save_invoice_persists_and_loads(self) -> None:
        number = self.db.save_invoice(
            self._client(),
            "2026-08-15",
            "2026-09-15",
            "notes",
            "terms",
            20.0,
            [self._item()],
        )
        self.assertEqual(number, 1)
        data = self.db.load_invoice(number)
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data["invoice_number"], 1)
        self.assertEqual(data["notes"], "notes")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0].amount, 20.0)
        self.assertEqual(data["tax_percent"], 20.0)
        self.assertEqual(len(self.db.list_invoices_overview()), 1)

    def test_ensure_client_updates_address_on_resave(self) -> None:
        n1 = self.db.save_invoice(
            self._client(address="Old Street", city="London"),
            "2026-01-01",
            "2026-02-01",
            "",
            "",
            0,
            [self._item("A")],
        )
        n2 = self.db.save_invoice(
            self._client(address="New Street 99", city="Manchester", name="Janet"),
            "2026-01-02",
            "2026-02-02",
            "",
            "",
            0,
            [self._item("B")],
        )
        d1 = self.db.load_invoice(n1)
        d2 = self.db.load_invoice(n2)
        assert d1 is not None and d2 is not None
        # Shared client master row must reflect latest Bill-to write.
        self.assertEqual(d1["client"].address, "New Street 99")
        self.assertEqual(d2["client"].address, "New Street 99")
        self.assertEqual(d2["client"].city, "Manchester")
        self.assertEqual(d2["client"].name, "JANET")
        self.assertEqual(d1["client"].id, d2["client"].id)

    def test_update_invoice_overwrites_items_and_header(self) -> None:
        number = self.db.save_invoice(
            self._client(),
            "2026-08-01",
            "2026-09-01",
            "old notes",
            "old terms",
            0,
            [self._item("Old", 1, 5)],
        )
        self.db.update_invoice(
            number,
            self._client(address="Updated Addr"),
            "2026-08-10",
            "2026-09-10",
            "new notes",
            "new terms",
            10.0,
            [self._item("New A", 3, 7), self._item("New B", 1, 2)],
        )
        data = self.db.load_invoice(number)
        assert data is not None
        self.assertEqual(data["invoice_number"], number)
        self.assertEqual(data["invoice_date"], "2026-08-10")
        self.assertEqual(data["notes"], "new notes")
        self.assertEqual(data["terms"], "new terms")
        self.assertEqual(data["tax_percent"], 10.0)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0].description, "New A")
        self.assertEqual(data["items"][0].amount, 21.0)
        self.assertEqual(data["client"].address, "Updated Addr")
        self.assertEqual(len(self.db.list_invoices_overview()), 1)

    def test_update_canceled_invoice_rejected(self) -> None:
        number = self.db.save_invoice(
            self._client(),
            "2026-08-01",
            "2026-09-01",
            "",
            "",
            0,
            [self._item()],
        )
        self.assertGreater(self.db.cancel_invoice(number), 0)
        with self.assertRaises(ValueError):
            self.db.update_invoice(
                number,
                self._client(),
                "2026-08-01",
                "2026-09-01",
                "",
                "",
                0,
                [self._item("X")],
            )

    def test_save_requires_items(self) -> None:
        with self.assertRaises(ValueError):
            self.db.save_invoice(
                self._client(),
                "2026-08-01",
                "2026-09-01",
                "",
                "",
                0,
                [],
            )


if __name__ == "__main__":
    unittest.main()
