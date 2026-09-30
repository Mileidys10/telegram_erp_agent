"""Servicio de logica de negocio para pedidos de venta y cotizaciones express."""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional, Tuple
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..domain.models import (
    AuditLog,
    Product,
    SalesOrder,
    SalesOrderItem,
    SalesOrderStatus,
    Stock,
    User,
    Warehouse,
    utc_now,
)
from .inventory_service import InventoryService


class SalesOrderService:
    """Gestion de cotizaciones, pedidos de venta y despacho de mercancia."""

    @staticmethod
    def create_quote(
        session: Session,
        user_id: int,
        customer_name: str,
        customer_tax_id: Optional[str],
        items: List[Dict[str, Any]],
    ) -> SalesOrder:
        """Crea una cotizacion o pedido express preliminar en estado COTIZACION."""
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario con ID {user_id} no encontrado.")

        # Generar correlativo unico
        year = datetime.now(timezone.utc).year
        total_orders = session.query(SalesOrder).count()
        order_number = f"PED-{year}-{total_orders + 1:04d}"

        subtotal_sum = 0.0
        order_items = []

        for item_data in items:
            sku = item_data.get("sku", "").strip().upper()
            qty = float(item_data.get("quantity", 0.0))
            if qty <= 0:
                raise ValueError(f"Cantidad invalida ({qty}) para el producto {sku}.")

            product = session.query(Product).filter(Product.sku == sku).first()
            if not product:
                raise ValueError(f"Producto con SKU '{sku}' no existe en el catalogo.")

            price = product.sale_price
            line_subtotal = round(qty * price, 2)
            subtotal_sum += line_subtotal

            order_item = SalesOrderItem(
                product_id=product.id,
                quantity=qty,
                unit_price=price,
                subtotal=line_subtotal,
            )
            order_items.append(order_item)

        tax_amount = round(subtotal_sum * 0.19, 2)  # 19% IVA
        total_amount = round(subtotal_sum + tax_amount, 2)

        sales_order = SalesOrder(
            order_number=order_number,
            customer_name=customer_name.strip(),
            customer_tax_id=customer_tax_id.strip() if customer_tax_id else None,
            subtotal_amount=subtotal_sum,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status=SalesOrderStatus.COTIZACION.value,
            created_by_id=user.id,
            items=order_items,
        )

        session.add(sales_order)

        # Registro de auditoria
        audit = AuditLog(
            telegram_user_id=user.telegram_user_id,
            action="CREAR_COTIZACION_VENTA",
            details=f"Cotizacion {order_number} para '{customer_name}' por total ${total_amount:.2f}",
        )
        session.add(audit)
        session.flush()

        return sales_order

    @staticmethod
    def confirm_and_dispatch_order(
        session: Session,
        order_id: int,
        warehouse_id: int,
        user_id: int,
    ) -> SalesOrder:
        """Confirma la cotizacion y descuenta inventario con asientos contables Kardex."""
        order = session.query(SalesOrder).filter(SalesOrder.id == order_id).first()
        if not order:
            raise ValueError(f"Pedido con ID {order_id} no encontrado.")

        if order.status != SalesOrderStatus.COTIZACION.value:
            raise ValueError(f"El pedido {order.order_number} ya se encuentra en estado '{order.status}'.")

        warehouse = session.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not warehouse:
            raise ValueError(f"Bodega con ID {warehouse_id} no encontrada.")

        # Descontar existencias de cada item
        for item in order.items:
            InventoryService.record_movement(
                session=session,
                sku=item.product.sku,
                warehouse_id=warehouse.id,
                movement_type="SALIDA",
                quantity=item.quantity,
                unit_cost=item.product.cost_price,
                reference=f"Venta Pedido {order.order_number}",
                user_id=user_id,
            )

        order.status = SalesOrderStatus.CONFIRMADO.value
        order.confirmed_at = utc_now()

        user = session.get(User, user_id)
        audit = AuditLog(
            telegram_user_id=user.telegram_user_id if user else None,
            action="CONFIRMAR_PEDIDO_VENTA",
            details=f"Pedido {order.order_number} confirmado y despachado desde {warehouse.code}",
        )
        session.add(audit)
        session.flush()

        return order

    @staticmethod
    def generate_sales_quote_pdf(
        session: Session,
        order_id: int,
        output_filepath: str,
        company_name: str = "Empresa Demo ERP S.A.",
    ) -> str:
        """Genera comprobante oficial en PDF de la cotizacion de venta."""
        order = session.query(SalesOrder).filter(SalesOrder.id == order_id).first()
        if not order:
            raise ValueError(f"Pedido con ID {order_id} no encontrado.")

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
            "DocTitle",
            parent=styles["Normal"],
            fontSize=16,
            leading=20,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1A365D"),
        )
        sub_style = ParagraphStyle(
            "SubTitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica",
            textColor=colors.HexColor("#4A5568"),
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
        )
        cell_normal = ParagraphStyle(
            "CellNormal",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica",
        )

        story = []

        # Encabezado
        story.append(Paragraph(f"{company_name} - Comprobante de Cotizacion", title_style))
        story.append(
            Paragraph(
                f"Pedido Nro: {order.order_number} | Estado: {order.status} | Fecha Emision: {order.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
                sub_style,
            )
        )
        story.append(
            Paragraph(
                f"Cliente: {order.customer_name} | Identificador Tributario: {order.customer_tax_id or 'Consumidor Final'}",
                sub_style,
            )
        )
        story.append(Spacer(1, 14))

        # Tabla de Items
        table_data = [
            [
                Paragraph("SKU", cell_bold),
                Paragraph("Descripcion", cell_bold),
                Paragraph("Cantidad", cell_bold),
                Paragraph("Precio Unit.", cell_bold),
                Paragraph("Subtotal", cell_bold),
            ]
        ]

        for item in order.items:
            table_data.append([
                Paragraph(item.product.sku, cell_normal),
                Paragraph(item.product.name, cell_normal),
                Paragraph(f"{item.quantity:.2f} {item.product.unit_measure}", cell_normal),
                Paragraph(f"${item.unit_price:.2f}", cell_normal),
                Paragraph(f"${item.subtotal:.2f}", cell_normal),
            ])

        # Fila de Totales
        table_data.append([
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("Subtotal Neto:", cell_bold),
            Paragraph(f"${order.subtotal_amount:.2f}", cell_bold),
        ])
        table_data.append([
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("IVA (19%):", cell_bold),
            Paragraph(f"${order.tax_amount:.2f}", cell_bold),
        ])
        table_data.append([
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("", cell_bold),
            Paragraph("TOTAL FINAL:", cell_bold),
            Paragraph(f"${order.total_amount:.2f}", cell_bold),
        ])

        col_widths = [70, 230, 80, 80, 80]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -4), 0.5, colors.HexColor("#CBD5E0")),
                ("LINEABOVE", (3, -3), (-1, -1), 0.5, colors.HexColor("#4A5568")),
                ("BACKGROUND", (3, -1), (-1, -1), colors.HexColor("#EDF2F7")),
            ])
        )

        story.append(table)
        story.append(Spacer(1, 15))
        story.append(
            Paragraph(
                "Documento emitido por el Agente Inteligente de Telegram ERP. Validez: 15 dias habiles.",
                sub_style,
            )
        )

        doc.build(story)
        return output_filepath
