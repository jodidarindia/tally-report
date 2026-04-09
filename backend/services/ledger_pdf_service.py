"""Tally-style Ledger PDF Generator for FLOWRA."""
import io
import os
from typing import List, Dict, Optional
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import logging

logger = logging.getLogger(__name__)

BRAND_BLUE = '#2563EB'
BRAND_DARK = '#0F1B4C'
HEADER_BG = '#1E3A5F'
LIGHT_BLUE = '#E8F0FE'
BORDER_GREY = '#B0BEC5'


def generate_tally_ledger_pdf(
    customer_name: str,
    company_name: str,
    entries: List[Dict],
    fy: str = '',
    customer_info: Dict = {}
) -> io.BytesIO:
    """Generate a Tally-style ledger PDF with running balance."""
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch
    )
    elements = []
    styles = getSampleStyleSheet()

    # -- Header: Company Name --
    company_style = ParagraphStyle(
        'CompanyName', parent=styles['Title'],
        textColor=colors.HexColor(BRAND_DARK),
        fontSize=16, alignment=TA_CENTER, spaceAfter=2
    )
    elements.append(Paragraph(f"<b>{company_name}</b>", company_style))

    # -- Sub-header: Ledger Account --
    ledger_style = ParagraphStyle(
        'LedgerTitle', parent=styles['Heading2'],
        textColor=colors.HexColor(HEADER_BG),
        fontSize=13, alignment=TA_CENTER, spaceAfter=2
    )
    elements.append(Paragraph(f"Ledger Account: <b>{customer_name}</b>", ledger_style))

    # -- Period line --
    period_text = f"FY: {fy}" if fy else "All Periods"
    group = customer_info.get('ledger_group', 'Sundry Debtors')
    state = customer_info.get('state', '')
    phone = customer_info.get('phone', '')
    info_parts = [f"Group: {group}"]
    if state:
        info_parts.append(f"State: {state}")
    if phone:
        info_parts.append(f"Ph: {phone}")

    info_style = ParagraphStyle(
        'InfoLine', parent=styles['Normal'],
        textColor=colors.HexColor('#546E7A'),
        fontSize=9, alignment=TA_CENTER, spaceAfter=4
    )
    elements.append(Paragraph(f"{period_text} | {' | '.join(info_parts)}", info_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER_GREY)))
    elements.append(Spacer(1, 0.15 * inch))

    # -- Table Header --
    col_widths = [1.0 * inch, 3.2 * inch, 1.0 * inch, 1.2 * inch,
                  1.2 * inch, 1.2 * inch, 1.4 * inch]

    header_row = ['Date', 'Particulars', 'Vch Type', 'Vch No.', 'Debit (Dr)', 'Credit (Cr)', 'Balance']

    table_data = [header_row]

    # -- Opening Balance --
    running_balance = 0.0
    table_data.append(['', 'Opening Balance', '', '', '', '', _fmt_amount(running_balance)])

    # -- Entries --
    total_debit = 0.0
    total_credit = 0.0

    for entry in entries:
        debit = entry.get('debit', 0) or 0
        credit = entry.get('credit', 0) or 0
        running_balance += debit - credit
        total_debit += debit
        total_credit += credit

        date_str = _format_date_display(entry.get('date', ''))
        table_data.append([
            date_str,
            entry.get('particulars', ''),
            entry.get('vch_type', ''),
            entry.get('vch_no', ''),
            _fmt_amount(debit) if debit else '',
            _fmt_amount(credit) if credit else '',
            _fmt_balance(running_balance)
        ])

    # -- Totals Row --
    table_data.append([
        '', 'Grand Total', '', '',
        _fmt_amount(total_debit),
        _fmt_amount(total_credit),
        _fmt_balance(running_balance)
    ])

    # -- Closing Balance Row --
    if running_balance >= 0:
        table_data.append(['', 'Closing Balance', '', '', '', _fmt_amount(running_balance), ''])
    else:
        table_data.append(['', 'Closing Balance', '', '', _fmt_amount(abs(running_balance)), '', ''])

    # -- Build Table --
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(HEADER_BG)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Opening Balance row
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F5F5F5')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Oblique'),

        # Data rows
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('FONTNAME', (0, 2), (-1, -3), 'Helvetica'),
        ('ALIGN', (4, 1), (6, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),

        # Totals row (second to last)
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor(LIGHT_BLUE)),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.HexColor(HEADER_BG)),

        # Closing Balance row (last)
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E3F2FD')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor(HEADER_BG)),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor(HEADER_BG)),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_GREY)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),

        # Alternating rows for data
        ('ROWBACKGROUNDS', (0, 2), (-1, -3), [colors.white, colors.HexColor('#FAFAFA')]),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    # -- Summary --
    summary_style = ParagraphStyle(
        'Summary', parent=styles['Normal'],
        textColor=colors.HexColor('#37474F'),
        fontSize=9, spaceAfter=3
    )
    elements.append(Paragraph(
        f"<b>Summary:</b> Sales: {len([e for e in entries if e['vch_type']=='Sales'])} | "
        f"Receipts: {len([e for e in entries if e['vch_type'] in ('Receipt','Payment')])} | "
        f"Credit Notes: {len([e for e in entries if e['vch_type']=='Credit Note'])} | "
        f"Journals: {len([e for e in entries if e['vch_type']=='Journal'])} | "
        f"Total Entries: {len(entries)}",
        summary_style
    ))

    # -- Footer --
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        textColor=colors.HexColor('#94A3B8'),
        fontSize=7, alignment=TA_CENTER
    )
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E0E0E0')))
    elements.append(Paragraph("Generated by FLOWRA | Organize. Automate. Accelerate.", footer_style))

    doc.build(elements)
    output.seek(0)
    return output


def _fmt_amount(val) -> str:
    """Format number as Indian currency string."""
    if val is None or val == 0:
        return ''
    try:
        return f"{float(val):,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_balance(val) -> str:
    """Format running balance with Dr/Cr suffix."""
    if val is None:
        return ''
    try:
        v = float(val)
        if v >= 0:
            return f"{v:,.2f} Dr"
        else:
            return f"{abs(v):,.2f} Cr"
    except (ValueError, TypeError):
        return str(val)


def _format_date_display(date_str: str) -> str:
    """Convert YYYY-MM-DD to DD-MMM-YYYY."""
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            return f"{parts[2]}-{months[int(parts[1])]}-{parts[0]}"
    except Exception:
        pass
    return date_str
