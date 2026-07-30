"""Prehliadač uložených faktúr — ekvivalent FrmInvoiceDB."""

from __future__ import annotations

from datetime import date
from calendar import monthcalendar, month_name
from pathlib import Path
from typing import Callable, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinter import ttk

import database as db
from config import COLORS, CURRENCY, FONT
from pdf_export import export_invoices_to_folder


class DatePickerField(ctk.CTkFrame):
    """Menší textbox + tlačidlo kalendára vpravo."""

    def __init__(
        self,
        master,
        initial: Optional[date] = None,
        on_change: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self.popup: Optional[ctk.CTkToplevel] = None
        self._view_year = (initial or date.today()).year
        self._view_month = (initial or date.today()).month

        self.entry = ctk.CTkEntry(
            self,
            height=32,
            width=120,
            corner_radius=8,
            border_color=COLORS["border"],
            fg_color=COLORS["surface_alt"],
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text"],
            justify="center",
        )
        self.entry.pack(side="left", fill="x", expand=True)
        if initial:
            self.entry.insert(0, initial.isoformat())

        self.btn = ctk.CTkButton(
            self,
            text="📅",
            width=36,
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(family=FONT, size=14),
            command=self._open_calendar,
        )
        self.btn.pack(side="right", padx=(6, 0))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def _current_date(self) -> date:
        parsed = db.parse_date(self.get())
        return parsed or date.today()

    def _open_calendar(self) -> None:
        current = self._current_date()
        self._view_year = current.year
        self._view_month = current.month
        self._show_popup()

    def _show_popup(self) -> None:
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()

        self.popup = ctk.CTkToplevel(self)
        self.popup.overrideredirect(True)
        self.popup.configure(fg_color=COLORS["surface"])
        self.popup.attributes("-topmost", True)
        self.popup.bind("<FocusOut>", lambda e: self.after(120, self._maybe_close))

        frame = ctk.CTkFrame(
            self.popup,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=10,
        )
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        nav = ctk.CTkFrame(frame, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkButton(
            nav,
            text="‹",
            width=30,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface_alt"],
            text_color=COLORS["text"],
            hover_color=COLORS["accent_soft"],
            command=self._prev_month,
        ).pack(side="left")
        self.lbl_month = ctk.CTkLabel(
            nav,
            text=f"{month_name[self._view_month]} {self._view_year}",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            text_color=COLORS["text"],
        )
        self.lbl_month.pack(side="left", expand=True)
        ctk.CTkButton(
            nav,
            text="›",
            width=30,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface_alt"],
            text_color=COLORS["text"],
            hover_color=COLORS["accent_soft"],
            command=self._next_month,
        ).pack(side="right")

        self.days_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.days_frame.pack(padx=8, pady=(0, 8))
        self._render_days()

        self.popup.update_idletasks()
        x = self.btn.winfo_rootx() - 180
        y = self.btn.winfo_rooty() + self.btn.winfo_height() + 4
        self.popup.geometry(f"260x250+{max(0, x)}+{y}")
        self.popup.focus_force()

    def _maybe_close(self) -> None:
        if self.popup is None or not self.popup.winfo_exists():
            return
        try:
            focused = self.popup.focus_get()
        except Exception:
            focused = None
        if focused is None:
            self.popup.destroy()
            self.popup = None

    def _prev_month(self) -> None:
        if self._view_month == 1:
            self._view_month = 12
            self._view_year -= 1
        else:
            self._view_month -= 1
        self._render_days()

    def _next_month(self) -> None:
        if self._view_month == 12:
            self._view_month = 1
            self._view_year += 1
        else:
            self._view_month += 1
        self._render_days()

    def _render_days(self) -> None:
        if not hasattr(self, "days_frame"):
            return
        for child in self.days_frame.winfo_children():
            child.destroy()

        self.lbl_month.configure(text=f"{month_name[self._view_month]} {self._view_year}")

        for i, day in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            ctk.CTkLabel(
                self.days_frame,
                text=day,
                width=30,
                font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                text_color=COLORS["text_muted"],
            ).grid(row=0, column=i, padx=1, pady=2)

        selected = self._current_date()
        today = date.today()
        weeks = monthcalendar(self._view_year, self._view_month)
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self.days_frame, text="", width=30, height=28).grid(
                        row=r, column=c, padx=1, pady=1
                    )
                    continue
                d = date(self._view_year, self._view_month, day)
                is_sel = d == selected
                is_today = d == today
                fg = COLORS["accent"] if is_sel else (
                    COLORS["accent_soft"] if is_today else COLORS["surface_alt"]
                )
                tc = "#FFFFFF" if is_sel else COLORS["text"]
                ctk.CTkButton(
                    self.days_frame,
                    text=str(day),
                    width=30,
                    height=28,
                    corner_radius=6,
                    fg_color=fg,
                    hover_color=COLORS["accent_hover"],
                    text_color=tc,
                    font=ctk.CTkFont(family=FONT, size=11),
                    command=lambda dd=d: self._pick(dd),
                ).grid(row=r, column=c, padx=1, pady=1)

    def _pick(self, d: date) -> None:
        self.set(d.isoformat())
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
            self.popup = None
        if self.on_change:
            self.on_change()


class SearchableCombo(ctk.CTkFrame):
    """Combo s písaním + live filtrovaním položiek."""

    MAX_VISIBLE = 12

    def __init__(self, master, on_change: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self.all_values: list[str] = ["(all)"]
        self.matches: list[str] = []
        self.selected_idx = 0
        self.popup: Optional[ctk.CTkToplevel] = None
        self._ignore = False

        self.entry = ctk.CTkEntry(
            self,
            height=32,
            corner_radius=8,
            border_color=COLORS["border"],
            fg_color=COLORS["surface_alt"],
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text"],
        )
        self.entry.pack(side="left", fill="x", expand=True)

        self.btn = ctk.CTkButton(
            self,
            text="▼",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(family=FONT, size=11),
            command=self._toggle_all,
        )
        self.btn.pack(side="right", padx=(4, 0))

        self.entry.insert(0, "(all)")
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Return>", self._confirm)
        self.entry.bind("<Escape>", lambda e: self.hide())
        self.entry.bind("<FocusOut>", lambda e: self.after(180, self.hide))

    def set_values(self, values: list[str]) -> None:
        self.all_values = ["(all)"] + [str(v) for v in values if str(v).strip()]
        self.set("(all)")

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self._ignore = True
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self._ignore = False

    def _toggle_all(self) -> None:
        text = self.get()
        if text in ("", "(all)"):
            self.matches = self.all_values[: self.MAX_VISIBLE]
        else:
            self.matches = self._filter(text)
            if not self.matches:
                self.matches = self.all_values[: self.MAX_VISIBLE]
        self.selected_idx = 0
        self._show()

    def _on_key(self, event) -> None:
        if self._ignore:
            return
        if event.keysym in (
            "Up",
            "Down",
            "Return",
            "Escape",
            "Tab",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Left",
            "Right",
            "Home",
            "End",
        ):
            return
        query = self.get()
        if query == "":
            self.matches = self.all_values[: self.MAX_VISIBLE]
        else:
            self.matches = self._filter(query)
        if not self.matches:
            self.hide()
            return
        self.selected_idx = 0
        self._show()

    def _filter(self, query: str) -> list[str]:
        q = query.upper()
        starts = [v for v in self.all_values if v.upper().startswith(q)]
        contains = [
            v for v in self.all_values if q in v.upper() and v not in starts
        ]
        return (starts + contains)[: self.MAX_VISIBLE]

    def _show(self) -> None:
        if self.popup is None or not self.popup.winfo_exists():
            self.popup = ctk.CTkToplevel(self)
            self.popup.overrideredirect(True)
            self.popup.configure(fg_color=COLORS["surface"])
            self.popup.attributes("-topmost", True)

        for child in self.popup.winfo_children():
            child.destroy()

        frame = ctk.CTkFrame(
            self.popup,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
        )
        frame.pack(fill="both", expand=True)

        self._buttons = []
        for i, value in enumerate(self.matches):
            btn = ctk.CTkButton(
                frame,
                text=value,
                anchor="w",
                height=28,
                corner_radius=0,
                fg_color=COLORS["accent_soft"] if i == self.selected_idx else COLORS["surface"],
                hover_color=COLORS["accent_soft"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(family=FONT, size=12),
                command=lambda v=value: self._pick(v),
            )
            btn.pack(fill="x")
            self._buttons.append(btn)

        self.popup.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        width = max(self.winfo_width(), 200)
        height = min(30 * len(self.matches) + 4, 360)
        self.popup.geometry(f"{width}x{height}+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()

    def _highlight(self) -> None:
        for i, btn in enumerate(getattr(self, "_buttons", [])):
            btn.configure(
                fg_color=COLORS["accent_soft"] if i == self.selected_idx else COLORS["surface"]
            )

    def _move(self, delta: int):
        if not self.matches or self.popup is None or not self.popup.winfo_exists():
            self._toggle_all()
            return "break"
        self.selected_idx = (self.selected_idx + delta) % len(self.matches)
        self._highlight()
        return "break"

    def _confirm(self, _event=None):
        if self.popup and self.popup.winfo_exists() and self.matches:
            self._pick(self.matches[self.selected_idx])
            return "break"
        if self.on_change:
            self.on_change()
        return None

    def _pick(self, value: str) -> None:
        self.set(value)
        self.hide()
        if self.on_change:
            self.on_change()

    def hide(self) -> None:
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.withdraw()


class InvoiceListWindow(ctk.CTkToplevel):
    def __init__(self, master, on_select: Callable[[int], None]):
        super().__init__(master)
        self.on_select = on_select
        self.title("List of Invoices")
        self.configure(fg_color=COLORS["bg"])
        self.transient(master)
        self.grab_set()
        self.minsize(1280, 780)

        self.all_rows: list[dict] = []
        self._build()
        self.refresh()
        # Najprv lift, potom center — spoľahlivejšie na Windows
        self.lift()
        self.focus_force()
        self.after(50, lambda: self._center_window(1360, 820))

    def _center_window(self, w: int, h: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(w, sw - 40)
        h = min(h, sh - 60)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(1280, w), min(780, h))

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            width=300,
        )
        left.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=16)

        ctk.CTkLabel(
            left,
            text="Sorting",
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=12, pady=(12, 8))

        self.cmb_surname = self._combo(left, "Surname:")
        self.cmb_company = self._combo(left, "Company:")
        self.cmb_city = self._combo(left, "City:")
        self.cmb_invoice = self._combo(left, "Invoice num:")

        ctk.CTkLabel(
            left,
            text="Date created from:",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self.date_from = DatePickerField(
            left,
            initial=date(date.today().year, 1, 1),
            on_change=self.apply_filter,
        )
        self.date_from.pack(fill="x", padx=12)

        ctk.CTkLabel(
            left,
            text="Date created to:",
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self.date_to = DatePickerField(
            left, initial=date.today(), on_change=self.apply_filter
        )
        self.date_to.pack(fill="x", padx=12)

        ctk.CTkButton(
            left,
            text="Refresh data",
            height=34,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            command=self.refresh,
        ).pack(fill="x", padx=12, pady=(16, 8))

        ctk.CTkButton(
            left,
            text="Apply filter",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["accent"],
            text_color=COLORS["accent"],
            hover_color=COLORS["accent_soft"],
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            command=self.apply_filter,
        ).pack(fill="x", padx=12, pady=(0, 12))

        stats = ctk.CTkFrame(left, fg_color=COLORS["surface_alt"], corner_radius=10)
        stats.pack(fill="x", padx=8, pady=(0, 12))

        ctk.CTkLabel(
            stats,
            text="Sum of not canceled",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", padx=12, pady=(12, 6))

        self.lbl_sub = self._stat(stats, "Sub Total:")
        self.lbl_total = self._stat(stats, "Total (tax):")
        self.lbl_count = self._stat(stats, "Invoices count:")
        self.lbl_top = self._stat(stats, "Top company:")
        self.lbl_parts = self._stat(stats, "Parts:")

        right = ctk.CTkFrame(
            self,
            fg_color=COLORS["surface"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text="Stored Invoices",
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            head,
            text="Generate PDF",
            width=140,
            height=34,
            corner_radius=8,
            fg_color="#0D9488",
            hover_color="#14B8A6",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            command=self._generate_pdfs,
        ).grid(row=0, column=1, sticky="e")

        table_wrap = ctk.CTkFrame(right, fg_color="transparent")
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_wrap.grid_columnconfigure(0, weight=1)
        table_wrap.grid_rowconfigure(0, weight=1)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Invoice.Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=28,
            font=(FONT, 10),
            borderwidth=0,
        )
        style.configure(
            "Invoice.Treeview.Heading",
            background=COLORS["header"],
            foreground="#FFFFFF",
            font=(FONT, 10, "bold"),
            relief="flat",
        )
        style.map("Invoice.Treeview", background=[("selected", COLORS["accent"])])

        cols = (
            "canceled",
            "number",
            "name",
            "surname",
            "company",
            "city",
            "date",
            "due",
            "amount",
            "tax",
        )
        self.tree = ttk.Treeview(
            table_wrap,
            columns=cols,
            show="headings",
            style="Invoice.Treeview",
            selectmode="extended",
        )
        headings = {
            "canceled": "CANCELED",
            "number": "NUMBER",
            "name": "NAME",
            "surname": "SURNAME",
            "company": "COMPANY",
            "city": "CITY",
            "date": "DATE",
            "due": "DUE",
            "amount": "AMOUNT",
            "tax": "TAX %",
        }
        widths = {
            "canceled": 80,
            "number": 70,
            "name": 90,
            "surname": 100,
            "company": 140,
            "city": 90,
            "date": 95,
            "due": 95,
            "amount": 90,
            "tax": 70,
        }
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")

        scroll_y = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<Double-1>", self._on_double_click)

        ctk.CTkLabel(
            right,
            text="Ctrl/Shift+click to select · Double-click to open · Generate PDF for selection",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=COLORS["text_muted"],
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))

    def _combo(self, parent, label: str) -> SearchableCombo:
        ctk.CTkLabel(
            parent,
            text=label,
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=12, pady=(6, 2))
        cmb = SearchableCombo(parent, on_change=self.apply_filter)
        cmb.pack(fill="x", padx=12)
        return cmb

    def _stat(self, parent, label: str) -> ctk.CTkLabel:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(side="left")
        val = ctk.CTkLabel(
            row,
            text="—",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=COLORS["text"],
            anchor="e",
        )
        val.pack(side="right")
        return val

    def refresh(self) -> None:
        self.all_rows = db.list_invoices_overview()
        self._fill_combos()
        self._reset_filters()
        self._fill_tree(self.all_rows)
        self._update_stats(self.all_rows, use_global=True)

    def _fill_combos(self) -> None:
        self.cmb_surname.set_values(db.distinct_values("surname"))
        self.cmb_company.set_values(db.distinct_values("company"))
        self.cmb_city.set_values(db.distinct_values("city"))
        self.cmb_invoice.set_values(db.distinct_values("invoice"))

    def _reset_filters(self) -> None:
        self.cmb_surname.set("(all)")
        self.cmb_company.set("(all)")
        self.cmb_city.set("(all)")
        self.cmb_invoice.set("(all)")
        self.date_from.set(date(date.today().year, 1, 1).isoformat())
        self.date_to.set(date.today().isoformat())

    @staticmethod
    def _match_text(field_value, query: str) -> bool:
        if query in ("", "(all)"):
            return True
        return query.upper() in str(field_value or "").upper()

    def apply_filter(self) -> None:
        surname = self.cmb_surname.get()
        company = self.cmb_company.get()
        city = self.cmb_city.get()
        inv = self.cmb_invoice.get()
        d_from = db.parse_date(self.date_from.get()) or date(date.today().year, 1, 1)
        d_to = db.parse_date(self.date_to.get()) or date.today()

        filtered = []
        for row in self.all_rows:
            if not self._match_text(row.get("surname"), surname):
                continue
            if not self._match_text(row.get("company"), company):
                continue
            if not self._match_text(row.get("city"), city):
                continue
            if not self._match_text(row.get("number"), inv):
                continue
            row_date = db.parse_date(row.get("date"))
            if row_date and not (d_from <= row_date <= d_to):
                continue
            filtered.append(row)

        self._fill_tree(filtered)
        self._update_stats(filtered, use_global=False)

    def _fill_tree(self, rows: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            canceled = "YES" if row.get("canceled") else ""
            amount = float(row.get("amount") or 0)
            tax = float(row.get("tax") or 0)
            self.tree.insert(
                "",
                "end",
                iid=str(row["number"]),
                values=(
                    canceled,
                    row.get("number"),
                    row.get("name"),
                    row.get("surname"),
                    row.get("company"),
                    row.get("city"),
                    str(row.get("date") or "")[:10],
                    str(row.get("due") or "")[:10],
                    f"{amount:,.2f}",
                    f"{tax:g}",
                ),
            )

    def _update_stats(self, rows: list[dict], use_global: bool) -> None:
        if use_global:
            s = db.stats_not_canceled()
            self.lbl_sub.configure(text=f"{CURRENCY}{s['subtotal']:,.2f}")
            self.lbl_total.configure(text=f"{CURRENCY}{s['tax_total']:,.2f}")
            self.lbl_count.configure(text=str(s["invoice_count"]))
            self.lbl_top.configure(text=str(s["top_company"]))
            self.lbl_parts.configure(text=str(s["top_count"]))
            return

        active = [r for r in rows if not r.get("canceled")]
        subtotal = sum(float(r.get("amount") or 0) for r in active)
        tax_total = sum(
            float(r.get("amount") or 0) * float(r.get("tax") or 0) / 100.0 for r in active
        )
        self.lbl_sub.configure(text=f"{CURRENCY}{subtotal:,.2f}")
        self.lbl_total.configure(text=f"{CURRENCY}{tax_total:,.2f}")
        self.lbl_count.configure(text=str(len(active)))

    def _selected_invoice_numbers(self) -> list[int]:
        numbers: list[int] = []
        for item_id in self.tree.selection():
            try:
                numbers.append(int(item_id))
            except ValueError:
                continue
        return numbers

    def _generate_pdfs(self) -> None:
        numbers = self._selected_invoice_numbers()
        if not numbers:
            visible = list(self.tree.get_children())
            if not visible:
                messagebox.showinfo("PDF", "No invoices to export.")
                return
            if not messagebox.askyesno(
                "PDF",
                "No rows selected.\nExport all currently visible invoices?",
            ):
                return
            numbers = []
            for item_id in visible:
                try:
                    numbers.append(int(item_id))
                except ValueError:
                    continue

        folder = filedialog.askdirectory(
            parent=self,
            title="Select folder to save PDF invoices",
            mustexist=True,
        )
        if not folder:
            return

        created, errors = export_invoices_to_folder(numbers, Path(folder))
        msg = f"Saved {len(created)} PDF file(s) to:\n{folder}"
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:8])
            if len(errors) > 8:
                msg += f"\n… and {len(errors) - 8} more"
            messagebox.showwarning("PDF", msg)
        else:
            messagebox.showinfo("PDF", msg)

    def _on_double_click(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            number = int(sel[0])
        except ValueError:
            return
        self.on_select(number)
        self.destroy()
