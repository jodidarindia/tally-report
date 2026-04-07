import csv
import io
import os
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import logging

logger = logging.getLogger(__name__)

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flowra-logo.png')
BRAND_COLOR = '#2563EB'
BRAND_COLOR_DARK = '#0F1B4C'
BG_STRIPE = '#F0F4FF'


class ExportService:
    """Service for exporting reports in various formats (PDF, Excel, CSV)"""

    @staticmethod
    def export_to_csv(data: List[Dict[str, Any]], filename: str = "report.csv") -> io.BytesIO:
        output = io.BytesIO()
        output_wrapper = io.TextIOWrapper(output, encoding='utf-8', newline='')
        if not data:
            return output
        fieldnames = list(data[0].keys())
        writer = csv.DictWriter(output_wrapper, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        output_wrapper.flush()
        output.seek(0)
        return output

    @staticmethod
    def export_to_excel(data: List[Dict[str, Any]], report_type: str = "Report") -> io.BytesIO:
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = report_type

        if not data:
            wb.save(output)
            output.seek(0)
            return output

        # FLOWRA blue header
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        stripe_fill = PatternFill(start_color="F0F4FF", end_color="F0F4FF", fill_type="solid")

        headers = list(data[0].keys())
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        for row_idx, row_data in enumerate(data, start=2):
            for col_idx, header in enumerate(headers, start=1):
                value = row_data.get(header, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                if isinstance(value, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
                # Alternating stripe
                if row_idx % 2 == 0:
                    cell.fill = stripe_fill

        for column_cells in ws.columns:
            length = max(len(str(cell.value)) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)

        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_to_pdf(data: List[Dict[str, Any]], report_type: str = "Report", title: str = "FLOWRA Report") -> io.BytesIO:
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()

        # Add logo if available
        if os.path.exists(LOGO_PATH):
            try:
                logo = Image(LOGO_PATH, width=1.8*inch, height=0.6*inch)
                logo.hAlign = 'LEFT'
                elements.append(logo)
                elements.append(Spacer(1, 0.15*inch))
            except Exception as e:
                logger.warning(f"Could not add logo to PDF: {e}")

        # Title
        title_style = ParagraphStyle(
            'FlowraTitle', parent=styles['Title'],
            textColor=colors.HexColor(BRAND_COLOR_DARK),
            fontSize=18, spaceAfter=6
        )
        elements.append(Paragraph(f"<b>{title}</b>", title_style))

        # Subtitle
        sub_style = ParagraphStyle(
            'FlowraSub', parent=styles['Heading2'],
            textColor=colors.HexColor(BRAND_COLOR),
            fontSize=12, spaceAfter=12
        )
        elements.append(Paragraph(f"{report_type} Report", sub_style))
        elements.append(Spacer(1, 0.15*inch))

        if not data:
            elements.append(Paragraph("No data available", styles['Normal']))
            doc.build(elements)
            output.seek(0)
            return output

        # Table
        headers = list(data[0].keys())
        table_data = [headers]
        for row in data:
            table_data.append([str(row.get(h, "")) for h in headers])

        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(BRAND_COLOR)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(BG_STRIPE)])
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))

        # Footer
        footer_style = ParagraphStyle(
            'FlowraFooter', parent=styles['Normal'],
            textColor=colors.HexColor('#94A3B8'),
            fontSize=7, alignment=1
        )
        elements.append(Paragraph("Generated by FLOWRA | Organize. Automate. Accelerate.", footer_style))

        doc.build(elements)
        output.seek(0)
        return output
