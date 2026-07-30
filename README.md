# Invoice v2.0

Modern desktop invoicing app (Python + CustomTkinter).

## Features

- **From** — supplier details (save with *Save From*; loaded on next start)
- **Bill to** — customer with database autocomplete
- **Invoice** — number, dates, Notes, Terms & Conditions
- **Items** — description, Qty, Rate, Amount + Sales Tax and Total
- **New / Save** — store invoices in SQLite
- **Open saved Invoices** — list, filters (including calendar), statistics
- **Generate PDF** — export selected invoices to a folder
- **Cancel invoice** — cancel a loaded invoice

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

```bash
pip install -r requirements.txt
```

## Run

```bash
python invoice.py
```

Or double-click: `spusti_invoice.bat`

## Project structure

| File | Description |
|------|-------------|
| `invoice.py` | Main application window |
| `invoice_list.py` | Saved invoices list + filters |
| `database.py` | SQLite CRUD |
| `pdf_export.py` | PDF generation (reportlab) |
| `config.py` | Paths, colors, defaults |
| `from_settings.json` | Saved From data (local, not in git) |
| `InvoiceDb.db` | Local SQLite DB (created on first start, not in git) |
| `spusti_invoice.bat` | Windows launcher |

## Database

The app uses a local `InvoiceDb.db` file in the project folder.  
If the file is missing at startup, it is created automatically with an empty schema.

## Quick start

1. Fill in **From** (your company details) and click **Save From**
2. In **Bill to**, start typing a name — pick a suggestion from the DB (if clients exist)
3. Add items, set tax, click **Save**
4. **Open saved Invoices** — filter, double-click to load
5. Select rows (Ctrl/Shift) → **Generate PDF** → choose a folder

## Privacy

Do not commit sensitive files: `from_settings.json`, `InvoiceDb.db`, `.env`, exported PDFs.
