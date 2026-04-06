import csv
import io
from typing import List, Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import logging

logger = logging.getLogger(__name__)

class ExportService:
    """
    Service for exporting reports in various formats (PDF, Excel, CSV)
    """
    
    @staticmethod
    def export_to_csv(data: List[Dict[str, Any]], filename: str = "report.csv") -> io.BytesIO:
        """Export data to CSV format"""
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
        """Export data to Excel format"""
        output = io.BytesIO()
        
        wb = Workbook()
        ws = wb.active
        ws.title = report_type
        
        if not data:
            wb.save(output)
            output.seek(0)
            return output
        
        # Header styling
        header_fill = PatternFill(start_color="064E3B", end_color="064E3B", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        # Write headers
        headers = list(data[0].keys())
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        
        # Write data
        for row_idx, row_data in enumerate(data, start=2):
            for col_idx, header in enumerate(headers, start=1):
                value = row_data.get(header, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                
                # Right-align numbers
                if isinstance(value, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
        
        # Auto-adjust column widths
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 50)
        
        wb.save(output)
        output.seek(0)
        return output
    
    @staticmethod
    def export_to_pdf(data: List[Dict[str, Any]], report_type: str = "Report", title: str = "Tally Report") -> io.BytesIO:
        """Export data to PDF format"""
        output = io.BytesIO()
        
        doc = SimpleDocTemplate(output, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_para = Paragraph(f"<b>{title}</b>", styles['Title'])
        elements.append(title_para)
        elements.append(Spacer(1, 0.3*inch))
        
        # Report type
        subtitle = Paragraph(f"<b>{report_type} Report</b>", styles['Heading2'])
        elements.append(subtitle)
        elements.append(Spacer(1, 0.2*inch))
        
        if not data:
            no_data_para = Paragraph("No data available", styles['Normal'])
            elements.append(no_data_para)
            doc.build(elements)
            output.seek(0)
            return output
        
        # Prepare table data
        headers = list(data[0].keys())
        table_data = [headers]
        
        for row in data:
            table_data.append([str(row.get(h, "")) for h in headers])
        
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#064E3B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FDFBF7')])
        ]))
        
        elements.append(table)
        
        doc.build(elements)
        output.seek(0)
        return output
