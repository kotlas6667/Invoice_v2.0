"""Application configuration for Invoice v2.0."""

from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "InvoiceDb.db"
FROM_SETTINGS_PATH = APP_DIR / "from_settings.json"

DEFAULT_COMPANY = {
    "company": "",
    "name": "",
    "address": "",
    "city": "",
    "zip": "",
    "country": "",
    "account": "",
    "sort_code": "",
}


def load_company() -> dict[str, str]:
    data = dict(DEFAULT_COMPANY)
    if FROM_SETTINGS_PATH.exists():
        try:
            saved = json.loads(FROM_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key in DEFAULT_COMPANY:
                    if key in saved and saved[key] is not None:
                        data[key] = str(saved[key])
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return data


def save_company(values: dict[str, str]) -> None:
    data = {key: str(values.get(key, "") or "") for key in DEFAULT_COMPANY}
    FROM_SETTINGS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


COMPANY = load_company()

DEFAULT_ITEM = ""
DEFAULT_CLIENT_COUNTRY = ""
DEFAULT_TAX_PERCENT = "0"
CURRENCY = "£"

COLORS = {
    "bg": "#F0F2F5",
    "surface": "#FFFFFF",
    "surface_alt": "#F7F8FA",
    "border": "#E2E5EB",
    "text": "#1A1D26",
    "text_muted": "#6B7280",
    "accent": "#0F766E",
    "accent_hover": "#0D9488",
    "accent_soft": "#CCFBF1",
    "header": "#134E4A",
    "danger": "#DC2626",
    "danger_bg": "#FEE2E2",
    "warning": "#B45309",
    "canceled": "#CD5C5C",
    "blue": "#2563EB",
    "amber": "#D97706",
}

FONT = "Segoe UI"
WIDTH, HEIGHT = 1100, 780
# Compact Items band (CTk height units): title + column header + ~1 row.
ITEMS_MIN_HEIGHT = 108
ITEMS_PREF_HEIGHT = 118
ITEMS_MAX_HEIGHT = 128
TOP_MAX_HEIGHT = 560
TOP_MIN_HEIGHT = 200
FOOTER_RESERVE = 96
HEADER_RESERVE = 62
LAYOUT_CHROME = 28
