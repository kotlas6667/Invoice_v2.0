"""
Invoice v2.0 — modern invoice desktop app.
"""

from __future__ import annotations

from datetime import date
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

import database as db
from config import (
    COLORS,
    COMPANY,
    CURRENCY,
    DEFAULT_CLIENT_COUNTRY,
    DEFAULT_ITEM,
    DEFAULT_TAX_PERCENT,
    FONT,
    HEIGHT,
    ITEMS_LIST_HEIGHT,
    WIDTH,
    load_company,
    save_company,
)
from invoice_list import InvoiceListWindow

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    relativedelta = None  # type: ignore


def _add_month(d: date) -> date:
    if relativedelta is not None:
        return d + relativedelta(months=1)
    month = d.month + 1
    year = d.year
    if month > 12:
        month = 1
        year += 1
    day = min(d.day, 28)
    return date(year, month, day)


class ClientAutocomplete:
    """Client suggestion dropdown while typing (Name / Surname / Company)."""

    MAX_ITEMS = 10

    def __init__(self, master: ctk.CTk, get_clients, on_select):
        self.master = master
        self.get_clients = get_clients
        self.on_select = on_select
        self.popup: Optional[ctk.CTkToplevel] = None
        self.buttons: list[ctk.CTkButton] = []
        self.matches: list[db.Client] = []
        self.selected_idx = 0
        self._ignore_change = False
        self.active_entry: Optional[ctk.CTkEntry] = None

    def bind_entry(self, entry: ctk.CTkEntry, mode: str) -> None:
        entry.bind("<KeyRelease>", lambda e, m=mode, ent=entry: self._on_key(e, ent, m))
        entry.bind("<Down>", lambda e: self._move(1))
        entry.bind("<Up>", lambda e: self._move(-1))
        entry.bind("<Return>", lambda e, ent=entry: self._confirm(e, ent))
        entry.bind("<Escape>", lambda e: self.hide())
        entry.bind("<FocusOut>", lambda e: self.master.after(150, self.hide))

    def _on_key(self, event, entry: ctk.CTkEntry, mode: str) -> None:
        if self._ignore_change:
            return
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self.active_entry = entry
        query = entry.get().strip()
        if len(query) < 1:
            self.hide()
            return
        self.matches = self._filter(query, mode)
        if not self.matches:
            self.hide()
            return
        self.selected_idx = 0
        self._show(entry)

    def _filter(self, query: str, mode: str) -> list[db.Client]:
        q = query.upper().strip()
        clients = self.get_clients()
        starts: list[db.Client] = []
        contains: list[db.Client] = []
        seen: set[int] = set()

        def add(bucket: list[db.Client], c: db.Client) -> None:
            cid = c.id if c.id is not None else id(c)
            if cid in seen:
                return
            seen.add(cid)
            bucket.append(c)

        for c in clients:
            name = (c.name or "").upper()
            surname = (c.surname or "").upper()
            company = (c.company or "").upper()
            combo = f"{name} - {surname}"

            if mode == "name":
                if name.startswith(q) or surname.startswith(q) or combo.startswith(q):
                    add(starts, c)
                elif q in name or q in surname or q in combo:
                    add(contains, c)
            elif mode == "surname":
                if surname.startswith(q):
                    add(starts, c)
                elif q in surname:
                    add(contains, c)
            elif mode == "company":
                if company.startswith(q):
                    add(starts, c)
                elif q in company:
                    add(contains, c)

        return (starts + contains)[: self.MAX_ITEMS]

    def _show(self, entry: ctk.CTkEntry) -> None:
        if self.popup is None or not self.popup.winfo_exists():
            self.popup = ctk.CTkToplevel(self.master)
            self.popup.overrideredirect(True)
            self.popup.configure(fg_color=COLORS["surface"])
            self.popup.attributes("-topmost", True)
            try:
                self.popup.transient(self.master)
            except Exception:
                pass

        for child in self.popup.winfo_children():
            child.destroy()
        self.buttons.clear()

        frame = ctk.CTkFrame(
            self.popup,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
        )
        frame.pack(fill="both", expand=True)

        for i, client in enumerate(self.matches):
            label = f"{client.name} - {client.surname}"
            if client.company:
                label += f"  ·  {client.company}"
            btn = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                height=30,
                corner_radius=0,
                fg_color=COLORS["accent_soft"] if i == self.selected_idx else COLORS["surface"],
                hover_color=COLORS["accent_soft"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(family=FONT, size=12),
                command=lambda c=client: self._pick(c),
            )
            btn.pack(fill="x", padx=1, pady=0)
            self.buttons.append(btn)

        self.popup.update_idletasks()
        x = entry.winfo_rootx()
        y = entry.winfo_rooty() + entry.winfo_height() + 2
        width = max(entry.winfo_width(), 320)
        height = min(34 * len(self.matches) + 4, 340)
        self.popup.geometry(f"{width}x{height}+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()

    def _highlight(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.configure(
                fg_color=COLORS["accent_soft"] if i == self.selected_idx else COLORS["surface"]
            )

    def _move(self, delta: int):
        if not self.matches or self.popup is None or not self.popup.winfo_exists():
            return "break"
        self.selected_idx = (self.selected_idx + delta) % len(self.matches)
        self._highlight()
        return "break"

    def _confirm(self, event, entry: ctk.CTkEntry):
        if self.popup and self.popup.winfo_exists() and self.matches:
            self._pick(self.matches[self.selected_idx])
            return "break"
        return None

    def _pick(self, client: db.Client) -> None:
        self._ignore_change = True
        self.hide()
        self.on_select(client)
        self.master.after(50, self._clear_ignore)

    def _clear_ignore(self) -> None:
        self._ignore_change = False

    def hide(self) -> None:
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.withdraw()



class Field(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        value: str = "",
        readonly: bool = False,
        width_label: int = 130,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self,
            text=label,
            width=width_label,
            anchor="w",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.entry = ctk.CTkEntry(
            self,
            height=30,
            corner_radius=8,
            fg_color=COLORS["surface_alt"] if not readonly else "#EEF0F3",
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            font=ctk.CTkFont(family=FONT, size=13),
            state="readonly" if readonly else "normal",
        )
        self.entry.grid(row=0, column=1, sticky="ew")
        if value:
            self.set(value)

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str) -> None:
        state = self.entry.cget("state")
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.entry.insert(0, value or "")
        self.entry.configure(state=state)

    def clear(self) -> None:
        self.set("")


class Section(ctk.CTkFrame):
    def __init__(self, master, title: str, accent: str = COLORS["accent"], **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["surface"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkFrame(head, width=4, height=18, corner_radius=2, fg_color=accent).pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkLabel(
            head,
            text=title,
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)


class InvoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Invoice")
        self.configure(fg_color=COLORS["bg"])
        self.minsize(900, 620)

        db.init_db()
        self.clients: list[db.Client] = []
        self.item_rows: list[dict] = []
        self.loaded_invoice: Optional[int] = None
        self.save_mode = "save"  # save | cancel

        self._build()
        self._fit_window_to_screen()
        self._reload_autocomplete()
        self._new_invoice(confirm=False)

    def _fit_window_to_screen(self) -> None:
        """Size window for short logical screens (1920x1080 @ 150% ≈ 1280x720)."""
        self.update_idletasks()
        sw = max(self.winfo_screenwidth(), 800)
        sh = max(self.winfo_screenheight(), 600)
        w = min(WIDTH, max(900, sw - 40))
        h = min(HEIGHT, max(620, sh - 80))
        self.minsize(min(900, w), min(620, h))
        self._center(w, h)

    def _center(self, w: int, h: int) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = max(0, (self.winfo_screenheight() // 2) - (h // 2))
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_header()
        # Entire form body scrolls so nothing is unreachable on short / scaled screens.
        self.main_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg"],
            corner_radius=0,
        )
        self.main_scroll.pack(fill="both", expand=True)
        self._body = self.main_scroll
        self._build_top_sections()
        self._build_items_section()
        self._build_footer()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=COLORS["header"], corner_radius=0, height=62)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=22, pady=12)
        ctk.CTkLabel(
            left,
            text="INVOICE",
            font=ctk.CTkFont(family=FONT, size=22, weight="bold"),
            text_color="#FFFFFF",
        ).pack(side="left")
        company_name = (load_company().get("company") or "").strip()
        self.lbl_header_company = ctk.CTkLabel(
            left,
            text=f"  {company_name}" if company_name else "",
            font=ctk.CTkFont(family=FONT, size=13),
            text_color="#5EEAD4",
        )
        self.lbl_header_company.pack(side="left", pady=(6, 0))

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e", padx=18)

        btn_kw = dict(
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
        )
        ctk.CTkButton(
            actions,
            text="Open saved Invoices",
            width=160,
            fg_color="transparent",
            border_width=1,
            border_color="#2DD4BF",
            text_color="#FFFFFF",
            hover_color="#115E59",
            command=self._open_list,
            **btn_kw,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            actions,
            text="New",
            width=80,
            fg_color=COLORS["accent_hover"],
            hover_color="#14B8A6",
            text_color="#FFFFFF",
            command=lambda: self._new_invoice(confirm=True),
            **btn_kw,
        ).pack(side="left", padx=4)

        self.btn_save = ctk.CTkButton(
            actions,
            text="Save",
            width=110,
            fg_color="#0D9488",
            hover_color="#14B8A6",
            text_color="#FFFFFF",
            command=self._on_save_click,
            **btn_kw,
        )
        self.btn_save.pack(side="left", padx=4)

        self.btn_cancel_invoice = ctk.CTkButton(
            actions,
            text="Cancel invoice",
            width=130,
            fg_color=COLORS["danger"],
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            command=self._cancel_invoice,
            **btn_kw,
        )
        # Visible only when a saved (non-canceled) invoice is loaded.
        self.btn_cancel_invoice.pack(side="left", padx=4)
        self.btn_cancel_invoice.pack_forget()

    def _build_top_sections(self) -> None:
        wrap = ctk.CTkFrame(self._body, fg_color="transparent")
        wrap.pack(fill="x", padx=16, pady=(14, 6))
        wrap.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")
        self.top_wrap = wrap

        # From / Company
        from_card = Section(wrap, "From", COLORS["accent"])
        from_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        company = load_company()
        self.fld_company = Field(from_card.body, "Company :", company["company"])
        self.fld_name = Field(from_card.body, "Name :", company["name"])
        self.fld_address = Field(from_card.body, "Company's Address :", company["address"])
        self.fld_city = Field(from_card.body, "City :", company["city"])
        self.fld_zip = Field(from_card.body, "Zip :", company["zip"])
        self.fld_country = Field(from_card.body, "Country :", company["country"])
        self.fld_account = Field(from_card.body, "Account nr. :", company["account"])
        self.fld_sort = Field(from_card.body, "Sort code :", company["sort_code"])
        for i, f in enumerate(
            [
                self.fld_company,
                self.fld_name,
                self.fld_address,
                self.fld_city,
                self.fld_zip,
                self.fld_country,
                self.fld_account,
                self.fld_sort,
            ]
        ):
            f.grid(row=i, column=0, sticky="ew", pady=2)

        ctk.CTkButton(
            from_card.body,
            text="Save From",
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._save_from_settings,
        ).grid(row=8, column=0, sticky="e", pady=(10, 0))

        # Bill to
        bill = Section(wrap, "Bill to", COLORS["blue"])
        bill.grid(row=0, column=1, sticky="nsew", padx=3)
        name_row = ctk.CTkFrame(bill.body, fg_color="transparent")
        name_row.grid(row=0, column=0, sticky="ew", pady=2)
        name_row.grid_columnconfigure((1, 2), weight=1)
        ctk.CTkLabel(
            name_row,
            text="Name and Surname:",
            width=130,
            anchor="w",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.txt_name_cst = ctk.CTkEntry(
            name_row,
            height=30,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONT, size=13),
        )
        self.txt_name_cst.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.txt_surname_cst = ctk.CTkEntry(
            name_row,
            height=30,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONT, size=13),
        )
        self.txt_surname_cst.grid(row=0, column=2, sticky="ew")

        self.fld_company_cst = Field(bill.body, "Company :")
        self.fld_address_cst = Field(bill.body, "Company's Address :")
        self.fld_city_cst = Field(bill.body, "City :")
        self.fld_zip_cst = Field(bill.body, "Zip :")
        self.fld_country_cst = Field(bill.body, "Country :", DEFAULT_CLIENT_COUNTRY)
        for i, f in enumerate(
            [
                self.fld_company_cst,
                self.fld_address_cst,
                self.fld_city_cst,
                self.fld_zip_cst,
                self.fld_country_cst,
            ]
        ):
            f.grid(row=i + 1, column=0, sticky="ew", pady=2)

        self.client_ac = ClientAutocomplete(
            self,
            get_clients=lambda: self.clients,
            on_select=self._fill_client,
        )
        self.client_ac.bind_entry(self.txt_name_cst, "name")
        self.client_ac.bind_entry(self.txt_surname_cst, "surname")
        self.client_ac.bind_entry(self.fld_company_cst.entry, "company")

        tip_row = ctk.CTkFrame(bill.body, fg_color="transparent")
        tip_row.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        tip_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tip_row,
            text="Tip: start typing — suggestions from DB (↑↓ Enter)",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            tip_row,
            text="Reset",
            width=70,
            height=28,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            hover_color=COLORS["danger_bg"],
            font=ctk.CTkFont(family=FONT, size=12),
            command=self._clear_bill_to,
        ).grid(row=0, column=1, sticky="e")

        # Invoice meta
        inv = Section(wrap, "Invoice", COLORS["amber"])
        inv.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.fld_invoice_no = Field(inv.body, "Invoice# :", readonly=True)
        self.fld_invoice_no.grid(row=0, column=0, sticky="ew", pady=2)

        self.lbl_canceled = ctk.CTkLabel(
            inv.body,
            text="",
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            text_color="#FFFFFF",
            fg_color=COLORS["canceled"],
            corner_radius=8,
            height=30,
        )
        self.lbl_canceled.grid(row=1, column=0, sticky="ew", pady=4)
        self.lbl_canceled.grid_remove()

        date_row = ctk.CTkFrame(inv.body, fg_color="transparent")
        date_row.grid(row=2, column=0, sticky="ew", pady=2)
        date_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            date_row,
            text="Invoice Date :",
            width=130,
            anchor="w",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.txt_invoice_date = ctk.CTkEntry(
            date_row,
            height=30,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONT, size=13),
        )
        self.txt_invoice_date.grid(row=0, column=1, sticky="ew")
        self.txt_invoice_date.bind("<FocusOut>", self._sync_due_date)
        self.txt_invoice_date.bind("<Return>", self._sync_due_date)

        due_row = ctk.CTkFrame(inv.body, fg_color="transparent")
        due_row.grid(row=3, column=0, sticky="ew", pady=2)
        due_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            due_row,
            text="Due Date :",
            width=130,
            anchor="w",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.txt_due_date = ctk.CTkEntry(
            due_row,
            height=30,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONT, size=13),
        )
        self.txt_due_date.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            inv.body,
            text="Notes",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=4, column=0, sticky="w", pady=(8, 2))
        self.txt_notes = ctk.CTkTextbox(
            inv.body,
            height=44,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            border_width=1,
            font=ctk.CTkFont(family=FONT, size=12),
        )
        self.txt_notes.grid(row=5, column=0, sticky="ew")

        ctk.CTkLabel(
            inv.body,
            text="Terms & Conditions",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=6, column=0, sticky="w", pady=(8, 2))
        self.txt_terms = ctk.CTkTextbox(
            inv.body,
            height=44,
            corner_radius=8,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            border_width=1,
            font=ctk.CTkFont(family=FONT, size=12),
        )
        self.txt_terms.grid(row=7, column=0, sticky="ew")

    def _build_items_section(self) -> None:
        self.items_card = ctk.CTkFrame(
            self._body,
            fg_color=COLORS["surface"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        card = self.items_card
        card.pack(fill="x", padx=16, pady=6)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 4))
        title = ctk.CTkFrame(head, fg_color="transparent")
        title.pack(side="left")
        ctk.CTkFrame(
            title, width=4, height=18, corner_radius=2, fg_color=COLORS["accent"]
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            title,
            text="Items",
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")
        ctk.CTkButton(
            head,
            text="+ Add item",
            width=110,
            height=30,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=lambda: self._add_item_row(DEFAULT_ITEM, "1", "0"),
        ).pack(side="right")

        header = ctk.CTkFrame(card, fg_color=COLORS["surface_alt"], corner_radius=8)
        header.pack(fill="x", padx=16, pady=(4, 0))
        self._cols(header)
        for i, (text, sticky) in enumerate(
            [
                ("#", "w"),
                ("Item Description", "ew"),
                ("Qty", "w"),
                ("Rate", "w"),
                ("Amount", "w"),
                ("", "w"),
            ]
        ):
            ctk.CTkLabel(
                header,
                text=text,
                font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                text_color=COLORS["text_muted"],
                anchor="w",
                width=40 if i == 0 else (0 if i == 1 else 90),
            ).grid(row=0, column=i, sticky=sticky, padx=6, pady=8)

        # Inner list scrolls only when many rows; the main window also scrolls.
        self.items_frame = ctk.CTkScrollableFrame(
            card,
            fg_color="transparent",
            height=ITEMS_LIST_HEIGHT,
        )
        self.items_frame.pack(fill="x", padx=10, pady=(4, 10))
        self.items_frame.grid_columnconfigure(0, weight=1)

    def _cols(self, frame: ctk.CTkFrame) -> None:
        frame.grid_columnconfigure(0, minsize=36, weight=0)
        frame.grid_columnconfigure(1, minsize=220, weight=1)
        frame.grid_columnconfigure(2, minsize=90, weight=0)
        frame.grid_columnconfigure(3, minsize=100, weight=0)
        frame.grid_columnconfigure(4, minsize=110, weight=0)
        frame.grid_columnconfigure(5, minsize=40, weight=0)

    def _build_footer(self) -> None:
        foot = ctk.CTkFrame(self._body, fg_color="transparent")
        foot.pack(fill="x", padx=16, pady=(4, 14))
        foot.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            foot,
            text="Invoice v2.0",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        totals = ctk.CTkFrame(
            foot,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        totals.grid(row=0, column=1, sticky="e")

        tax_row = ctk.CTkFrame(totals, fg_color="transparent")
        tax_row.grid(row=1, column=0, columnspan=2, sticky="e", padx=12, pady=2)
        ctk.CTkLabel(
            tax_row,
            text="Sales Tax (",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).pack(side="left")
        self.txt_tax = ctk.CTkEntry(
            tax_row,
            width=50,
            height=28,
            corner_radius=6,
            justify="right",
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONT, size=12),
        )
        self.txt_tax.pack(side="left")
        self.txt_tax.insert(0, DEFAULT_TAX_PERCENT)
        self.txt_tax.bind("<KeyRelease>", lambda e: self._recalc_totals())
        ctk.CTkLabel(
            tax_row,
            text=f")%   {CURRENCY}",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).pack(side="left")
        self.lbl_tax_amount = ctk.CTkLabel(
            tax_row,
            text="0.00",
            width=90,
            anchor="e",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            text_color=COLORS["text"],
        )
        self.lbl_tax_amount.pack(side="left")

        self.lbl_subtotal = self._total_label(totals, "Sub Total", "0.00", 0)
        self.lbl_total = self._total_label(totals, "Total", "0.00", 2, bold=True)

    def _total_label(self, parent, label, value, row, bold=False):
        weight = "bold" if bold else "normal"
        color = COLORS["accent"] if bold else COLORS["text_muted"]
        ctk.CTkLabel(
            parent,
            text=f"{label}  {CURRENCY}",
            font=ctk.CTkFont(family=FONT, size=13 if bold else 12, weight=weight),
            text_color=color,
            anchor="e",
            width=120,
        ).grid(row=row, column=0, padx=(14, 8), pady=3, sticky="e")
        lbl = ctk.CTkLabel(
            parent,
            text=value,
            font=ctk.CTkFont(family=FONT, size=13 if bold else 12, weight=weight),
            text_color=COLORS["accent"] if bold else COLORS["text"],
            anchor="e",
            width=90,
        )
        lbl.grid(row=row, column=1, padx=(0, 14), pady=3, sticky="e")
        return lbl

    # ── Items ───────────────────────────────────────────────────────────────

    def _clear_items(self) -> None:
        for row in list(self.item_rows):
            row["frame"].destroy()
        self.item_rows.clear()

    def _add_item_row(self, desc: str = "", qty: str = "1", rate: str = "0") -> None:
        idx = len(self.item_rows)
        frame = ctk.CTkFrame(self.items_frame, fg_color="transparent")
        frame.grid(row=idx, column=0, sticky="ew", pady=2)
        self._cols(frame)

        entry_kw = dict(
            height=30,
            corner_radius=6,
            fg_color=COLORS["surface_alt"],
            border_color=COLORS["border"],
            border_width=1,
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text"],
        )

        num = ctk.CTkLabel(
            frame,
            text=str(idx + 1),
            width=36,
            text_color=COLORS["text_muted"],
            font=ctk.CTkFont(family=FONT, size=12),
        )
        num.grid(row=0, column=0, padx=4)

        desc_e = ctk.CTkEntry(frame, **entry_kw)
        desc_e.grid(row=0, column=1, sticky="ew", padx=4)
        desc_e.insert(0, desc)

        qty_e = ctk.CTkEntry(frame, width=90, justify="right", **entry_kw)
        qty_e.grid(row=0, column=2, padx=4)
        qty_e.insert(0, qty)

        rate_e = ctk.CTkEntry(frame, width=100, justify="right", **entry_kw)
        rate_e.grid(row=0, column=3, padx=4)
        rate_e.insert(0, rate)

        amount_l = ctk.CTkLabel(
            frame,
            text="0.00",
            width=110,
            anchor="e",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            text_color=COLORS["text"],
        )
        amount_l.grid(row=0, column=4, padx=4)

        row = {
            "frame": frame,
            "num": num,
            "desc": desc_e,
            "qty": qty_e,
            "rate": rate_e,
            "amount": amount_l,
        }

        def on_change(_=None):
            self._recalc_row(row)
            self._recalc_totals()

        for e in (qty_e, rate_e):
            e.bind("<KeyRelease>", on_change)
            e.bind("<FocusOut>", on_change)

        ctk.CTkButton(
            frame,
            text="×",
            width=32,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLORS["danger_bg"],
            text_color=COLORS["danger"],
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            command=lambda r=row: self._remove_item(r),
        ).grid(row=0, column=5, padx=4)

        self.item_rows.append(row)
        self._recalc_row(row)
        self._recalc_totals()
        self._renumber()

    def _remove_item(self, row: dict) -> None:
        if len(self.item_rows) <= 1:
            messagebox.showinfo("Items", "Invoice must contain at least one item.")
            return
        row["frame"].destroy()
        self.item_rows.remove(row)
        self._renumber()
        self._recalc_totals()

    def _renumber(self) -> None:
        for i, row in enumerate(self.item_rows):
            row["num"].configure(text=str(i + 1))
            row["frame"].grid(row=i, column=0, sticky="ew", pady=2)

    @staticmethod
    def _parse_float(text: str) -> float:
        try:
            return float((text or "0").replace(",", ".").strip())
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_int(text: str) -> int:
        try:
            return int(float((text or "0").replace(",", ".").strip()))
        except ValueError:
            return 0

    def _recalc_row(self, row: dict) -> float:
        qty = self._parse_float(row["qty"].get())
        rate = self._parse_float(row["rate"].get())
        amount = qty * rate
        row["amount"].configure(text=f"{amount:,.2f}")
        row["_amount"] = amount
        return amount

    def _recalc_totals(self) -> None:
        subtotal = sum(self._recalc_row(r) for r in self.item_rows)
        tax_txt = self.txt_tax.get().strip() or "0"
        if not self.txt_tax.get().strip():
            self.txt_tax.delete(0, "end")
            self.txt_tax.insert(0, "0")
        tax_pct = self._parse_float(tax_txt)
        tax_amount = (subtotal / 100.0) * tax_pct
        total = subtotal + tax_amount
        self.lbl_subtotal.configure(text=f"{subtotal:,.2f}")
        self.lbl_tax_amount.configure(text=f"{tax_amount:,.2f}")
        self.lbl_total.configure(text=f"{total:,.2f}")

    # ── Client autocomplete ─────────────────────────────────────────────────

    def _reload_autocomplete(self) -> None:
        self.clients = db.load_clients()

    def _save_from_settings(self) -> None:
        values = {
            "company": self.fld_company.get(),
            "name": self.fld_name.get(),
            "address": self.fld_address.get(),
            "city": self.fld_city.get(),
            "zip": self.fld_zip.get(),
            "country": self.fld_country.get(),
            "account": self.fld_account.get(),
            "sort_code": self.fld_sort.get(),
        }
        try:
            save_company(values)
            COMPANY.update(values)
            company_name = (values.get("company") or "").strip()
            if hasattr(self, "lbl_header_company"):
                self.lbl_header_company.configure(
                    text=f"  {company_name}" if company_name else ""
                )
            messagebox.showinfo("From", "From settings saved.\nThey will load automatically next time.")
        except OSError as exc:
            messagebox.showerror("From", f"Could not save settings:\n{exc}")

    def _fill_client(self, client: db.Client) -> None:
        self.txt_name_cst.delete(0, "end")
        self.txt_name_cst.insert(0, client.name)
        self.txt_surname_cst.delete(0, "end")
        self.txt_surname_cst.insert(0, client.surname)
        self.fld_company_cst.set(client.company)
        self.fld_address_cst.set(client.address)
        self.fld_city_cst.set(client.city)
        self.fld_zip_cst.set(client.zip)
        self.fld_country_cst.set(client.country or DEFAULT_CLIENT_COUNTRY)

    def _clear_bill_to(self) -> None:
        if hasattr(self, "client_ac"):
            self.client_ac.hide()
        self.txt_name_cst.delete(0, "end")
        self.txt_surname_cst.delete(0, "end")
        self.fld_company_cst.clear()
        self.fld_address_cst.clear()
        self.fld_city_cst.clear()
        self.fld_zip_cst.clear()
        self.fld_country_cst.set(DEFAULT_CLIENT_COUNTRY)

    # ── Flows ───────────────────────────────────────────────────────────────

    def _sync_due_date(self, _event=None) -> None:
        d = db.parse_date(self.txt_invoice_date.get())
        if d:
            due = _add_month(d)
            self.txt_due_date.delete(0, "end")
            self.txt_due_date.insert(0, due.isoformat())

    def _new_invoice(self, confirm: bool = True) -> None:
        if confirm:
            if not messagebox.askyesno("New", "Do you want to new invoice ?"):
                return
        self.loaded_invoice = None
        self.save_mode = "save"
        self.btn_save.configure(
            text="Save",
            state="normal",
            fg_color="#0D9488",
            hover_color="#14B8A6",
        )
        self.btn_cancel_invoice.pack_forget()
        self.lbl_canceled.grid_remove()
        self.fld_invoice_no.clear()

        # Clear customer (Country zostáva podľa originálu čiastočne — tu reset na England)
        self.txt_name_cst.delete(0, "end")
        self.txt_surname_cst.delete(0, "end")
        self.fld_company_cst.clear()
        self.fld_address_cst.clear()
        self.fld_city_cst.clear()
        self.fld_zip_cst.clear()
        self.fld_country_cst.set(DEFAULT_CLIENT_COUNTRY)

        today = date.today()
        self.txt_invoice_date.delete(0, "end")
        self.txt_invoice_date.insert(0, today.isoformat())
        self.txt_due_date.delete(0, "end")
        self.txt_due_date.insert(0, _add_month(today).isoformat())
        self.txt_notes.delete("1.0", "end")
        self.txt_terms.delete("1.0", "end")
        self.txt_tax.delete(0, "end")
        self.txt_tax.insert(0, DEFAULT_TAX_PERCENT)

        self._clear_items()
        self._add_item_row(DEFAULT_ITEM, "1", "0")
        self._recalc_totals()

    def _validate(self) -> bool:
        if not self.txt_surname_cst.get().strip():
            messagebox.showwarning("Validation", "Surname is required.")
            return False
        if not self.fld_company_cst.get().strip():
            messagebox.showwarning("Validation", "Company is required.")
            return False
        if not self.item_rows:
            messagebox.showwarning("Validation", "Add at least one item.")
            return False
        for row in self.item_rows:
            if not row["desc"].get().strip():
                messagebox.showwarning("Validation", "Item description is required.")
                row["desc"].configure(border_color=COLORS["danger"])
                return False
            qty = self._parse_int(row["qty"].get())
            rate = self._parse_float(row["rate"].get())
            if qty < 1:
                messagebox.showerror("Error value", "Qty must be integer ≥ 1")
                return False
            if rate <= 0:
                messagebox.showerror("Error value", "Rate must be greater than 0")
                return False
        return True

    def _collect_client(self) -> db.Client:
        return db.Client(
            id=None,
            name=self.txt_name_cst.get(),
            surname=self.txt_surname_cst.get(),
            company=self.fld_company_cst.get(),
            address=self.fld_address_cst.get(),
            city=self.fld_city_cst.get(),
            zip=self.fld_zip_cst.get(),
            country=self.fld_country_cst.get(),
        )

    def _collect_items(self) -> list[db.InvoiceItem]:
        tax = self._parse_float(self.txt_tax.get())
        items: list[db.InvoiceItem] = []
        for row in self.item_rows:
            qty = self._parse_int(row["qty"].get())
            rate = self._parse_float(row["rate"].get())
            items.append(
                db.InvoiceItem(
                    description=row["desc"].get().strip(),
                    qty=qty,
                    rate=rate,
                    amount=qty * rate,
                    sales_tax=tax,
                )
            )
        return items

    def _set_actions_for_invoice(self, *, canceled: bool) -> None:
        """Save always writes; Cancel invoice is a separate action."""
        self.save_mode = "save"
        self.btn_cancel_invoice.pack_forget()
        if canceled:
            self.btn_save.configure(state="disabled")
            return
        self.btn_save.configure(
            text="Save",
            state="normal",
            fg_color="#0D9488",
            hover_color="#14B8A6",
        )
        if self.loaded_invoice is not None:
            self.btn_cancel_invoice.pack(side="left", padx=4)

    def _on_save_click(self) -> None:
        self._save_invoice()

    def _save_invoice(self) -> None:
        if not self._validate():
            return
        try:
            client = self._collect_client()
            items = self._collect_items()
            invoice_date = self.txt_invoice_date.get().strip()
            due_date = self.txt_due_date.get().strip()
            notes = self.txt_notes.get("1.0", "end").strip()
            terms = self.txt_terms.get("1.0", "end").strip()
            tax_percent = self._parse_float(self.txt_tax.get())

            if self.loaded_invoice is not None:
                number = db.update_invoice(
                    invoice_number=self.loaded_invoice,
                    client=client,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    notes=notes,
                    terms=terms,
                    tax_percent=tax_percent,
                    items=items,
                )
            else:
                number = db.save_invoice(
                    client=client,
                    invoice_date=invoice_date,
                    due_date=due_date,
                    notes=notes,
                    terms=terms,
                    tax_percent=tax_percent,
                    items=items,
                )
            self.fld_invoice_no.set(str(number))
            self.loaded_invoice = number
            self._reload_autocomplete()
            self._set_actions_for_invoice(canceled=False)
            messagebox.showinfo("Data", "Data written")
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _cancel_invoice(self) -> None:
        if self.loaded_invoice is None:
            return
        if not messagebox.askyesno(
            "Cancel", f"Cancel invoice #{self.loaded_invoice}?"
        ):
            return
        updated = db.cancel_invoice(self.loaded_invoice)
        if updated > 0:
            messagebox.showinfo("Canceled", "Successful Canceled !")
            self.lbl_canceled.configure(text="CANCELED")
            self.lbl_canceled.grid()
            self._set_actions_for_invoice(canceled=True)
        else:
            messagebox.showwarning("Canceled", "Unsuccessful operation Canceled !")

    def _open_list(self) -> None:
        InvoiceListWindow(self, on_select=self._load_invoice)

    def _load_invoice(self, invoice_number: int) -> None:
        data = db.load_invoice(invoice_number)
        if not data:
            messagebox.showwarning("Load", f"Invoice #{invoice_number} not found.")
            return

        self._new_invoice(confirm=False)
        self.loaded_invoice = invoice_number
        self.fld_invoice_no.set(str(invoice_number))
        self._fill_client(data["client"])

        self.txt_invoice_date.delete(0, "end")
        self.txt_invoice_date.insert(0, str(data["invoice_date"] or "")[:10])
        self.txt_due_date.delete(0, "end")
        self.txt_due_date.insert(0, str(data["due_date"] or "")[:10])
        self.txt_notes.delete("1.0", "end")
        self.txt_notes.insert("1.0", data["notes"])
        self.txt_terms.delete("1.0", "end")
        self.txt_terms.insert("1.0", data["terms"])
        self.txt_tax.delete(0, "end")
        self.txt_tax.insert(0, str(data["tax_percent"]).rstrip("0").rstrip(".") or "0")

        self._clear_items()
        for item in data["items"]:
            self._add_item_row(item.description, str(item.qty), f"{item.rate:g}")
        self._recalc_totals()

        if data["canceled"]:
            self.lbl_canceled.configure(text="CANCELED")
            self.lbl_canceled.grid()
            self._set_actions_for_invoice(canceled=True)
        else:
            self.lbl_canceled.grid_remove()
            self._set_actions_for_invoice(canceled=False)


if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()
