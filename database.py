"""SQLite layer — schema and CRUD for Invoice v2.0."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator, Optional

from config import DB_PATH


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> bool:
    """Create InvoiceDb.db (and tables) if missing. Returns True if a new file was created."""
    created_new = not DB_PATH.exists()
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS invoiceBaseInfo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                companyClient TEXT,
                addressClient TEXT,
                cityClient TEXT,
                zipClient TEXT,
                countryClient TEXT,
                nameClient TEXT,
                surnameClient TEXT
            );

            CREATE TABLE IF NOT EXISTS invoiceDatas (
                invoiceNumber INTEGER PRIMARY KEY AUTOINCREMENT,
                id INTEGER NOT NULL,
                invoiceDate TEXT,
                invoiceDue TEXT,
                notes TEXT,
                termsCondit TEXT,
                FOREIGN KEY (id) REFERENCES invoiceBaseInfo(id)
            );

            CREATE TABLE IF NOT EXISTS itemsValues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                itemDesc TEXT,
                itemQty INTEGER,
                itemRate REAL,
                itemAmount REAL,
                salesTax REAL,
                idInvoice INTEGER NOT NULL,
                canceled INTEGER DEFAULT 0,
                FOREIGN KEY (idInvoice) REFERENCES invoiceDatas(invoiceNumber)
            );

            CREATE VIEW IF NOT EXISTS View_Max_Company AS
            SELECT
                b.companyClient AS Company,
                COUNT(d.invoiceNumber) AS pocetInvoices
            FROM invoiceBaseInfo b
            JOIN invoiceDatas d ON d.id = b.id
            JOIN itemsValues i ON i.idInvoice = d.invoiceNumber
            WHERE COALESCE(i.canceled, 0) = 0
            GROUP BY b.companyClient
            ORDER BY pocetInvoices DESC
            LIMIT 1;
            """
        )
    return created_new


def _upper(value: str) -> str:
    return (value or "").strip().upper()


@dataclass
class Client:
    id: Optional[int]
    name: str
    surname: str
    company: str
    address: str
    city: str
    zip: str
    country: str

    @property
    def autocomplete_key(self) -> str:
        return f"{_upper(self.name)} - {_upper(self.surname)}"


@dataclass
class InvoiceItem:
    description: str
    qty: int
    rate: float
    amount: float
    sales_tax: float


@dataclass
class InvoiceHeader:
    invoice_number: Optional[int]
    client_id: int
    invoice_date: str
    due_date: str
    notes: str
    terms: str


def load_clients() -> list[Client]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM invoiceBaseInfo ORDER BY surnameClient").fetchall()
    return [
        Client(
            id=r["id"],
            name=r["nameClient"] or "",
            surname=r["surnameClient"] or "",
            company=r["companyClient"] or "",
            address=r["addressClient"] or "",
            city=r["cityClient"] or "",
            zip=r["zipClient"] or "",
            country=r["countryClient"] or "",
        )
        for r in rows
    ]


def find_client(surname: str, company: str) -> Optional[Client]:
    s, c = _upper(surname), _upper(company)
    for client in load_clients():
        if _upper(client.surname) == s and _upper(client.company) == c:
            return client
    return None


def insert_client(client: Client) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoiceBaseInfo
            (companyClient, addressClient, cityClient, zipClient, countryClient, nameClient, surnameClient)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _upper(client.company),
                client.address.strip(),
                client.city.strip(),
                client.zip.strip(),
                client.country.strip(),
                _upper(client.name),
                _upper(client.surname),
            ),
        )
        return int(cur.lastrowid)


def ensure_client(client: Client) -> int:
    existing = find_client(client.surname, client.company)
    if existing and existing.id is not None:
        # Konflikt: rovnaké priezvisko, iná firma už by našiel iný záznam;
        # tu kontrolujeme či firma sedí — find_client už vyžaduje oboje.
        return existing.id
    # Kontrola konfliktu priezviska s inou firmou
    for other in load_clients():
        if _upper(other.surname) == _upper(client.surname) and _upper(other.company) != _upper(client.company):
            raise ValueError(
                "Surname has diferent Company name !!!!, Please change Surname"
            )
    return insert_client(client)


def save_invoice(
    client: Client,
    invoice_date: str,
    due_date: str,
    notes: str,
    terms: str,
    tax_percent: float,
    items: list[InvoiceItem],
) -> int:
    client_id = ensure_client(client)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoiceDatas (id, invoiceDate, invoiceDue, notes, termsCondit)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_id, invoice_date, due_date, notes, terms),
        )
        invoice_number = int(cur.lastrowid)
        for item in items:
            conn.execute(
                """
                INSERT INTO itemsValues
                (itemDesc, itemQty, itemRate, itemAmount, salesTax, idInvoice, canceled)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    item.description,
                    item.qty,
                    item.rate,
                    item.amount,
                    tax_percent,
                    invoice_number,
                ),
            )
    return invoice_number


def cancel_invoice(invoice_number: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE itemsValues SET canceled = 1 WHERE idInvoice = ?",
            (invoice_number,),
        )
        return cur.rowcount


def load_invoice(invoice_number: int) -> Optional[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                b.id AS client_id,
                b.nameClient, b.surnameClient, b.companyClient,
                b.addressClient, b.cityClient, b.zipClient, b.countryClient,
                d.invoiceNumber, d.invoiceDate, d.invoiceDue, d.notes, d.termsCondit,
                i.itemDesc, i.itemQty, i.itemRate, i.itemAmount, i.salesTax, i.canceled
            FROM invoiceBaseInfo b
            INNER JOIN invoiceDatas d ON b.id = d.id
            INNER JOIN itemsValues i ON i.idInvoice = d.invoiceNumber
            WHERE d.invoiceNumber = ?
            """,
            (invoice_number,),
        ).fetchall()

    if not rows:
        return None

    first = rows[0]
    return {
        "client": Client(
            id=first["client_id"],
            name=first["nameClient"] or "",
            surname=first["surnameClient"] or "",
            company=first["companyClient"] or "",
            address=first["addressClient"] or "",
            city=first["cityClient"] or "",
            zip=first["zipClient"] or "",
            country=first["countryClient"] or "",
        ),
        "invoice_number": first["invoiceNumber"],
        "invoice_date": first["invoiceDate"],
        "due_date": first["invoiceDue"],
        "notes": first["notes"] or "",
        "terms": first["termsCondit"] or "",
        "tax_percent": float(first["salesTax"] or 0),
        "canceled": bool(first["canceled"]),
        "items": [
            InvoiceItem(
                description=r["itemDesc"] or "",
                qty=int(r["itemQty"] or 0),
                rate=float(r["itemRate"] or 0),
                amount=float(r["itemAmount"] or 0),
                sales_tax=float(r["salesTax"] or 0),
            )
            for r in rows
        ],
    }


def list_invoices_overview() -> list[dict[str, Any]]:
    """Jeden riadok na faktúru (ako GROUP BY v C# prehliadači)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                MAX(i.canceled) AS canceled,
                d.invoiceNumber AS number,
                b.nameClient AS name,
                b.surnameClient AS surname,
                b.companyClient AS company,
                b.addressClient AS address,
                b.cityClient AS city,
                b.zipClient AS zip,
                b.countryClient AS country,
                d.invoiceDate AS date,
                d.invoiceDue AS due,
                d.notes AS notes,
                d.termsCondit AS conditions,
                GROUP_CONCAT(i.itemDesc, '; ') AS descript,
                SUM(i.itemQty) AS qty,
                SUM(i.itemRate) AS rate,
                SUM(i.itemAmount) AS amount,
                MAX(i.salesTax) AS tax
            FROM invoiceBaseInfo b
            INNER JOIN invoiceDatas d ON b.id = d.id
            INNER JOIN itemsValues i ON i.idInvoice = d.invoiceNumber
            GROUP BY d.invoiceNumber
            ORDER BY d.invoiceNumber DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def distinct_values(column: str) -> list[str]:
    mapping = {
        "surname": ("invoiceBaseInfo", "surnameClient"),
        "company": ("invoiceBaseInfo", "companyClient"),
        "city": ("invoiceBaseInfo", "cityClient"),
        "invoice": ("invoiceDatas", "invoiceNumber"),
    }
    table, col = mapping[column]
    with connect() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) != '' ORDER BY {col}"
        ).fetchall()
    return [str(r[0]) for r in rows]


def stats_not_canceled() -> dict[str, Any]:
    with connect() as conn:
        sub = conn.execute(
            "SELECT COALESCE(SUM(itemAmount), 0) FROM itemsValues WHERE canceled = 0"
        ).fetchone()[0]
        # Opravené: peňažná daň = SUM(amount * tax%/100), nie súčet percent
        tax_money = conn.execute(
            """
            SELECT COALESCE(SUM(itemAmount * salesTax / 100.0), 0)
            FROM itemsValues WHERE canceled = 0
            """
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(DISTINCT idInvoice) FROM itemsValues WHERE canceled = 0"
        ).fetchone()[0]
        top = conn.execute("SELECT Company, pocetInvoices FROM View_Max_Company").fetchone()

    return {
        "subtotal": float(sub or 0),
        "tax_total": float(tax_money or 0),
        "invoice_count": int(count or 0),
        "top_company": top["Company"] if top else "—",
        "top_count": int(top["pocetInvoices"]) if top else 0,
    }


def parse_date(value: str | date | datetime | None) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None
