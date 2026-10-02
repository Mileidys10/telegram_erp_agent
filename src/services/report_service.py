"""Servicio de generacion de reportes ejecutivos en PDF con ReportLab."""

from datetime import datetime, timezone
import os
from typing import List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..domain.models import KardexMovement, Product, Stock


class ReportService:
    """Compilador de documentos PDF para informes de inventario y ERP."""

    @staticmethod
    def generate_inventory_valuation_pdf(
        session: Session,
        output_filepath: str,
        company_name: str = "Empresa Demo ERP S.A.",
        requested_by: str = "Telegram User",
    ) -> str:
        """Genera un informe formal en PDF con la valorizacion del stock actual."""
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        doc = SimpleDocTemplate(
            output_filepath,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A2B4C"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#556677"),
            spaceAfter=12,
        )
        cell_style = ParagraphStyle(
            "CellNormal",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
        )

        story = []

        # 1. Encabezado Corporativo
        story.append(Paragraph(f"{company_name} - Sistema ERP", title_style))
        story.append(
            Paragraph(
                f"Reporte: Valorizacion de Inventario Fisico | Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Solicitante: {requested_by}",
                subtitle_style,
            )
        )
        story.append(Spacer(1, 10))

        # 2. Extraccion de datos
        products = session.query(Product).order_by(Product.category, Product.name).all()

        table_data = [
            [
                Paragraph("SKU", cell_bold),
                Paragraph("Producto", cell_bold),
                Paragraph("Categoria", cell_bold),
                Paragraph("Stock Total", cell_bold),
                Paragraph("Costo Unit.", cell_bold),
                Paragraph("Valor Total", cell_bold),
                Paragraph("Estado", cell_bold),
            ]
        ]

        grand_total_units = 0.0
        grand_total_valuation = 0.0

        for p in products:
            stocks = session.query(Stock).filter(Stock.product_id == p.id).all()
            total_qty = sum(s.quantity for s in stocks)
            total_val = total_qty * p.cost_price

            grand_total_units += total_qty
            grand_total_valuation += total_val

            status_desc = "CRITICO" if total_qty <= p.stock_minimo else "NORMAL"

            table_data.append([
                Paragraph(p.sku, cell_style),
                Paragraph(p.name[:30], cell_style),
                Paragraph(p.category, cell_style),
                Paragraph(f"{total_qty:.1f} {p.unit_measure}", cell_style),
                Paragraph(f"${p.cost_price:.2f}", cell_style),
                Paragraph(f"${total_val:.2f}", cell_style),
                Paragraph(status_desc, cell_bold if status_desc == "CRITICO" else cell_style),
            ])

        # Fila de Totales
        table_data.append([
            Paragraph("TOTALES", cell_bold),
            Paragraph(f"{len(products)} articulos", cell_bold),
            Paragraph("-", cell_style),
            Paragraph(f"{grand_total_units:.1f}", cell_bold),
            Paragraph("-", cell_style),
            Paragraph(f"${grand_total_valuation:.2f}", cell_bold),
            Paragraph("-", cell_style),
        ])

        # 3. Estilizado de Tabla
        col_widths = [65, 150, 75, 70, 60, 65, 55]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(t)

        # 4. Pie de Documento
        story.append(Spacer(1, 15))
        story.append(
            Paragraph(
                "Documento emitido automaticamente por el Agente de Telegram ERP. Firma y validacion electronica activa.",
                subtitle_style,
            )
        )

        doc.build(story)
        return output_filepath

    @staticmethod
    def generate_kardex_pdf(
        session: Session,
        product_sku: str,
        output_filepath: str,
        company_name: str = "Empresa Demo ERP S.A.",
        requested_by: str = "Telegram User",
    ) -> str:
        """Genera un informe formal en PDF con los movimientos de Kardex de un producto."""
        product = session.query(Product).filter(Product.sku == product_sku.upper()).first()
        if not product:
            raise ValueError(f"Producto con SKU '{product_sku}' no encontrado.")

        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        doc = SimpleDocTemplate(
            output_filepath,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "KardexTitle",
            parent=styles["Normal"],
            fontSize=15,
            leading=18,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0F172A"),
        )
        sub_style = ParagraphStyle(
            "KardexSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica",
            textColor=colors.HexColor("#475569"),
        )
        cell_bold = ParagraphStyle(
            "KCellBold",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
        )
        cell_normal = ParagraphStyle(
            "KCellNormal",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
            fontName="Helvetica",
        )

        story = []

        # Encabezado
        story.append(Paragraph(f"{company_name} - Trazabilidad de Kardex", title_style))
        story.append(
            Paragraph(
                f"Articulo: [{product.sku}] {product.name} | Categoria: {product.category} | U.M.: {product.unit_measure}",
                sub_style,
            )
        )
        story.append(
            Paragraph(
                f"Fecha de Emision: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Solicitado por: {requested_by}",
                sub_style,
            )
        )
        story.append(Spacer(1, 12))

        # Movimientos
        movements = (
            session.query(KardexMovement)
            .filter(KardexMovement.product_id == product.id)
            .order_by(KardexMovement.timestamp.asc())
            .all()
        )

        table_data = [
            [
                Paragraph("Fecha / Hora", cell_bold),
                Paragraph("Tipo", cell_bold),
                Paragraph("Bodega", cell_bold),
                Paragraph("Cantidad", cell_bold),
                Paragraph("Costo U.", cell_bold),
                Paragraph("Total Costo", cell_bold),
                Paragraph("Saldo", cell_bold),
                Paragraph("Referencia", cell_bold),
                Paragraph("Usuario", cell_bold),
            ]
        ]

        for m in movements:
            table_data.append([
                Paragraph(m.timestamp.strftime("%Y-%m-%d %H:%M"), cell_normal),
                Paragraph(m.movement_type, cell_normal),
                Paragraph(m.warehouse.code if m.warehouse else "-", cell_normal),
                Paragraph(f"{m.quantity:+.1f}", cell_normal),
                Paragraph(f"${m.unit_cost:.2f}", cell_normal),
                Paragraph(f"${m.total_cost:.2f}", cell_normal),
                Paragraph(f"{m.balance_quantity:.1f}", cell_normal),
                Paragraph(m.reference[:25], cell_normal),
                Paragraph(m.user.username if m.user else "Sys", cell_normal),
            ])

        col_widths = [75, 45, 45, 45, 45, 55, 45, 125, 60]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284C7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(t)
        story.append(Spacer(1, 15))
        story.append(
            Paragraph(
                "Documento de control interno y auditoria contable de inventario ERP.",
                sub_style,
            )
        )

        doc.build(story)
        return output_filepath
