"""PDF invoice export (reportlab)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import CURRENCY, load_company
import database as db


def _money(value: float) -> str:
    return f"{CURRENCY}{value:,.2f}"


def _safe(text: Any) -> str:
    s = str(text or "").strip()
    if s.upper() in ("NULL", "NONE"):
        return ""
    return s


def build_invoice_pdf(invoice_number: int, output_path: Path) -> Path:
    data = db.load_invoice(invoice_number)
    if not data:
        raise ValueError(f"Invoice #{invoice_number} not found")

    company = load_company()
    client = data["client"]
    items = data["items"]
    tax_pct = float(data.get("tax_percent") or 0)
    subtotal = sum(float(i.amount) for i in items)
    tax_amount = subtotal * tax_pct / 100.0
    total = subtotal + tax_amount
    canceled = bool(data.get("canceled"))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Invoice {invoice_number}",
        author=company["company"],
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvTitle",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#134E4A"),
        spaceAfter=6,
    )
    section_style = ParagraphStyle(
        "InvSection",
        parent=styles["Heading3"],
        fontSize=11,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "InvBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1A1D26"),
    )
    muted = ParagraphStyle(
        "InvMuted",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
    )
    danger = ParagraphStyle(
        "InvCanceled",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#DC2626"),
        alignment=1,
    )

    story: list = []
    story.append(Paragraph("INVOICE", title_style))
    story.append(Paragraph(f"Invoice # {_safe(invoice_number)}", body))
    story.append(
        Paragraph(
            f"Date: {_safe(str(data.get('invoice_date') or '')[:10])}"
            f" &nbsp;&nbsp; Due: {_safe(str(data.get('due_date') or '')[:10])}",
            muted,
        )
    )
    if canceled:
        story.append(Spacer(1, 6))
        story.append(Paragraph("CANCELED", danger))

    story.append(Paragraph("From", section_style))
    from_lines = [
        company["company"],
        company["name"],
        company["address"],
        f"{company['city']}, {company['zip']}",
        company["country"],
        f"Account: {company['account']}  ·  Sort code: {company['sort_code']}",
    ]
    story.append(Paragraph("<br/>".join(_safe(x) for x in from_lines), body))

    story.append(Paragraph("Bill to", section_style))
    bill_lines = [
        f"{_safe(client.name)} {_safe(client.surname)}".strip(),
        _safe(client.company),
        _safe(client.address),
        f"{_safe(client.city)}, {_safe(client.zip)}".strip(", "),
        _safe(client.country),
    ]
    story.append(Paragraph("<br/>".join(x for x in bill_lines if x), body))

    story.append(Paragraph("Items", section_style))
    table_data = [["#", "Description", "Qty", "Rate", "Amount"]]
    for idx, item in enumerate(items, start=1):
        table_data.append(
            [
                str(idx),
                _safe(item.description),
                str(item.qty),
                _money(float(item.rate)),
                _money(float(item.amount)),
            ]
        )

    table = Table(table_data, colWidths=[20 * mm, 90 * mm, 20 * mm, 28 * mm, 28 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#134E4A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E5EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    totals = [
        ["Sub Total", _money(subtotal)],
        [f"Sales Tax ({tax_pct:g}%)", _money(tax_amount)],
        ["Total", _money(total)],
    ]
    tot_table = Table(totals, colWidths=[140 * mm, 46 * mm])
    tot_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#0F766E")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(tot_table)

    notes = _safe(data.get("notes"))
    terms = _safe(data.get("terms"))
    if notes:
        story.append(Paragraph("Notes", section_style))
        story.append(Paragraph(notes.replace("\n", "<br/>"), body))
    if terms:
        story.append(Paragraph("Terms & Conditions", section_style))
        story.append(Paragraph(terms.replace("\n", "<br/>"), body))

    story.append(Spacer(1, 18))
    footer_name = _safe(company.get("company")) or "Invoice"
    story.append(Paragraph(f"{footer_name} · Invoice v2.0", muted))

    doc.build(story)
    return output_path


def export_invoices_to_folder(invoice_numbers: list[int], folder: Path) -> tuple[list[Path], list[str]]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    errors: list[str] = []
    for number in invoice_numbers:
        path = folder / f"Invoice_{number}.pdf"
        try:
            build_invoice_pdf(number, path)
            created.append(path)
        except Exception as exc:
            errors.append(f"#{number}: {exc}")
    return created, errors
