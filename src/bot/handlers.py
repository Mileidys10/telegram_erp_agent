"""Manejadores de comandos, logica conversacional y respuestas de Telegram."""

from datetime import datetime, timezone
import os
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from ..domain.models import AuditLog, UserRole
from ..services.auth_service import AuthService
from ..services.inventory_service import InventoryService
from ..services.nlp_service import NLPService
from ..services.purchase_order_service import PurchaseOrderService
from ..services.report_service import ReportService
from ..services.sales_order_service import SalesOrderService


class BotCommandHandler:
    """Procesador agnostico de comandos y mensajes de Telegram para integracion ERP."""

    @staticmethod
    def handle_start(telegram_user_id: int, session: Session) -> str:
        """Responde al comando /start con mensaje de bienvenida y estado de vinculacion."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if user:
            return (
                f"Bienvenido de nuevo, {user.full_name}.\n"
                f"Rol activo: {user.role}\n\n"
                "Comandos disponibles:\n"
                "- /stock <SKU o nombre> : Consultar stock\n"
                "- /mover_stock : Registrar movimiento Kardex\n"
                "- /kardex <SKU> : Ver ultimos movimientos\n"
                "- /alertas : Ver productos con stock critico\n"
                "- /ordenes : Ver ordenes de compra pendientes\n"
                "- /pedido <cliente> <SKU> <cant> : Emitir cotizacion de venta express\n"
                "- /confirmar_pedido <id> <bodega_id> : Despachar y descontar inventario\n"
                "- /reporte : Descargar informe PDF de inventario\n"
                "- /reporte_kardex <SKU> : Descargar trazabilidad contable en PDF\n"
                "- O simplemente escribe tu consulta en lenguaje natural."
            )
        return (
            "Bienvenido al Agente de Gestion ERP.\n\n"
            "Tu cuenta de Telegram aun no esta vinculada al sistema corporativo.\n"
            "Para vincularte, solicita un codigo OTP de 6 digitos a tu administrador y envia:\n"
            "/vincular <CODIGO_OTP>"
        )

    @staticmethod
    def handle_link(telegram_user_id: int, otp_code: str, session: Session) -> str:
        """Procesa la vinculacion de cuenta mediante OTP."""
        try:
            user = AuthService.link_telegram_user(session, telegram_user_id, otp_code)
            return (
                f"Vinculacion exitosa.\n"
                f"Usuario: {user.username}\n"
                f"Colaborador: {user.full_name}\n"
                f"Rol asignado: {user.role}\n\n"
                "Ya puedes utilizar todos los comandos autorizados para tu rol."
            )
        except ValueError as e:
            return f"Error de vinculacion: {e}"

    @staticmethod
    def handle_stock(telegram_user_id: int, query_text: str, session: Session) -> str:
        """Consulta el stock de uno o mas articulos."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta con /vincular <CODIGO_OTP>."

        clean_query = query_text.strip()
        if not clean_query:
            return "Uso: /stock <SKU o nombre del producto>"

        # Intentar coincidencia exacta de SKU primero
        summary = InventoryService.get_product_stock_summary(session, clean_query)
        if summary:
            status_tag = "[ALERTA: STOCK CRITICO]" if summary["is_critical"] else "[STOCK NORMAL]"
            wh_lines = "\n".join(
                f"  - {w['warehouse_code']} ({w['warehouse_name']}): {w['available']} disp. / {w['quantity']} fis."
                for w in summary["warehouses"]
            )
            return (
                f"FICHA DE INVENTARIO: {summary['sku']} {status_tag}\n"
                f"Producto: {summary['name']}\n"
                f"Categoria: {summary['category']}\n"
                f"Stock Total Disponible: {summary['available_quantity']} {summary['unit_measure']}\n"
                f"Stock Total Fisico: {summary['total_quantity']} {summary['unit_measure']}\n"
                f"Stock Comprometido: {summary['total_reserved']} {summary['unit_measure']}\n"
                f"Punto de Reorden: {summary['stock_minimo']} {summary['unit_measure']}\n"
                f"Precio Venta: ${summary['sale_price']:.2f}\n\n"
                f"Distribucion por Bodega:\n{wh_lines if wh_lines else '  (Sin existencias registradas)'}"
            )

        # Busqueda aproximada
        matches = InventoryService.search_products(session, clean_query, limit=5)
        if not matches:
            return f"No se encontraron productos que coincidan con '{clean_query}'."

        lines = [f"Resultados encontrados para '{clean_query}':"]
        for p in matches:
            s_sum = InventoryService.get_product_stock_summary(session, p.sku)
            disp = s_sum["available_quantity"] if s_sum else 0.0
            crit = " [CRITICO]" if (s_sum and s_sum["is_critical"]) else ""
            lines.append(f"- {p.sku}: {p.name} | Disp: {disp} {p.unit_measure}{crit}")

        lines.append("\nPara ver el detalle completo, escribe: /stock <SKU>")
        return "\n".join(lines)

    @staticmethod
    def handle_mover_stock(
        telegram_user_id: int,
        sku: str,
        warehouse_id: int,
        movement_type: str,
        quantity: float,
        unit_cost: float,
        reference: str,
        session: Session,
    ) -> str:
        """Registra un movimiento en el Kardex validando permisos."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        if not AuthService.has_role(session, telegram_user_id, [UserRole.ALMACENERO.value, UserRole.ADMIN.value]):
            return "Permiso denegado. Se requiere rol ALMACENERO o ADMIN para mover inventario."

        try:
            mov, new_balance = InventoryService.record_movement(
                session=session,
                sku=sku,
                warehouse_id=warehouse_id,
                movement_type=movement_type,
                quantity=quantity,
                unit_cost=unit_cost,
                reference=reference,
                user_id=user.id,
                telegram_user_id=telegram_user_id,
            )
            return (
                f"MOVIMIENTO REGISTRADO CON EXITO EN KARDEX\n"
                f"ID Asiento: #{mov.id}\n"
                f"Tipo: {mov.movement_type}\n"
                f"SKU: {sku}\n"
                f"Cantidad: {mov.quantity}\n"
                f"Almacen ID: {warehouse_id}\n"
                f"Referencia: {mov.reference}\n"
                f"Nuevo Stock Total: {new_balance} unidades\n"
                f"Fecha: {mov.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        except Exception as e:
            return f"Error al procesar movimiento: {e}"

    @staticmethod
    def handle_kardex(telegram_user_id: int, sku: str, session: Session) -> str:
        """Visualiza los ultimos asientos de Kardex de un articulo."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        if not sku:
            return "Uso: /kardex <SKU>"

        history = InventoryService.get_kardex_history(session, sku, limit=7)
        if not history:
            return f"No existen registros de movimientos para el SKU '{sku}'."

        lines = [f"HISTORIAL RECIENTE KARDEX: {sku}"]
        for h in history:
            lines.append(
                f"- #{h['id']} [{h['timestamp']}] {h['movement_type']}: {h['quantity']} unid. | "
                f"Saldo: {h['balance']} | Ref: {h['reference']} | Por: {h['user_name']}"
            )
        return "\n".join(lines)

    @staticmethod
    def handle_alertas(telegram_user_id: int, session: Session) -> str:
        """Muestra la lista de productos en quiebre o stock critico."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        critical = InventoryService.get_critical_stock_items(session)
        if not critical:
            return "ESTADO DE INVENTARIO OPTIMO: No hay ningun producto por debajo de su stock minimo."

        lines = [f"ALERTAS DE STOCK CRITICO ({len(critical)} articulos):"]
        for c in critical:
            lines.append(
                f"- {c['sku']} ({c['name']}): Stock actual: {c['current_stock']} {c['unit_measure']} "
                f"(Minimo: {c['stock_minimo']} | Deficit: {c['deficit']})"
            )
        return "\n".join(lines)

    @staticmethod
    def handle_ordenes_pendientes(telegram_user_id: int, session: Session) -> str:
        """Lista las ordenes de compra pendientes de aprobacion."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        orders = PurchaseOrderService.get_pending_orders(session)
        if not orders:
            return "No hay ordenes de compra pendientes de aprobacion."

        lines = ["ORDENES DE COMPRA PENDIENTES:"]
        for o in orders:
            lines.append(
                f"- #{o['id']} {o['order_number']} | Proveedor: {o['supplier_name']} | "
                f"Monto: ${o['total_amount']:.2f} | Fecha: {o['created_at']}\n"
                f"  Para aprobar: /aprobar {o['id']}\n"
                f"  Para rechazar: /rechazar {o['id']} <motivo>"
            )
        return "\n\n".join(lines)

    @staticmethod
    def handle_aprobar_orden(telegram_user_id: int, order_id: int, session: Session) -> str:
        """Aprueba una orden de compra validando rol gerencial."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        try:
            order = PurchaseOrderService.approve_order(session, order_id, user.id, telegram_user_id)
            return (
                f"ORDEN DE COMPRA APROBADA EXITOSAMENTE\n"
                f"Numero: {order.order_number}\n"
                f"Proveedor: {order.supplier_name}\n"
                f"Monto: ${order.total_amount:.2f}\n"
                f"Aprobada por: {user.full_name} ({user.role})\n"
                f"Fecha: {order.approved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        except Exception as e:
            return f"Error al aprobar orden: {e}"

    @staticmethod
    def handle_rechazar_orden(telegram_user_id: int, order_id: int, reason: str, session: Session) -> str:
        """Rechaza una orden de compra registrando motivo."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        if not reason.strip():
            return "Uso: /rechazar <ID_ORDEN> <motivo obligatorio>"

        try:
            order = PurchaseOrderService.reject_order(session, order_id, user.id, reason, telegram_user_id)
            return (
                f"ORDEN DE COMPRA RECHAZADA\n"
                f"Numero: {order.order_number}\n"
                f"Motivo registrado: {order.rejection_reason}\n"
                f"Rechazada por: {user.full_name}\n"
                f"Fecha: {order.approved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        except Exception as e:
            return f"Error al rechazar orden: {e}"

    @staticmethod
    def handle_reporte(telegram_user_id: int, session: Session, output_dir: str = "reports") -> Tuple[str, Optional[str]]:
        """Genera el reporte ejecutivo de valorizacion en PDF."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta.", None

        if not AuthService.has_role(session, telegram_user_id, [UserRole.GERENTE.value, UserRole.ADMIN.value]):
            return "Permiso denegado. Se requiere rol GERENTE o ADMIN para descargar reportes de valorizacion.", None

        filename = f"reporte_inventario_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(output_dir, filename)

        try:
            ReportService.generate_inventory_valuation_pdf(
                session=session,
                output_filepath=filepath,
                company_name="Empresa ERP Corp S.A.",
                requested_by=f"{user.full_name} ({user.role})",
            )
            return f"Reporte de valorizacion generado con exito. Archivo: {filename}", filepath
        except Exception as e:
            return f"Error al compilar reporte PDF: {e}", None

    @staticmethod
    def handle_reporte_kardex(telegram_user_id: int, sku: str, session: Session, output_dir: str = "reports") -> Tuple[str, Optional[str]]:
        """Genera el reporte en PDF con la trazabilidad contable de Kardex."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta.", None

        clean_sku = sku.strip().upper()
        if not clean_sku:
            return "Uso: /reporte_kardex <SKU>", None

        filename = f"kardex_{clean_sku}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(output_dir, filename)

        try:
            ReportService.generate_kardex_pdf(
                session=session,
                product_sku=clean_sku,
                output_filepath=filepath,
                company_name="Empresa ERP Corp S.A.",
                requested_by=f"{user.full_name} ({user.role})",
            )
            return f"Reporte de Kardex para '{clean_sku}' generado con exito. Archivo: {filename}", filepath
        except Exception as e:
            return f"Error al generar Kardex en PDF: {e}", None

    @staticmethod
    def handle_pedido(
        telegram_user_id: int,
        customer_name: str,
        sku: str,
        quantity: float,
        session: Session,
    ) -> str:
        """Crea una cotizacion o pedido express para un cliente."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        if not AuthService.has_role(session, telegram_user_id, [UserRole.VENDEDOR.value, UserRole.GERENTE.value, UserRole.ADMIN.value]):
            return "Permiso denegado. Se requiere rol VENDEDOR, GERENTE o ADMIN para emitir pedidos."

        try:
            items = [{"sku": sku.strip().upper(), "quantity": quantity}]
            order = SalesOrderService.create_quote(
                session=session,
                user_id=user.id,
                customer_name=customer_name.strip(),
                customer_tax_id=None,
                items=items,
            )
            return (
                f"COTIZACION DE VENTA EMITIDA: {order.order_number}\n"
                f"Cliente: {order.customer_name}\n"
                f"Articulo: {sku.upper()} x {quantity:.1f}\n"
                f"Subtotal: ${order.subtotal_amount:.2f}\n"
                f"IVA (19%): ${order.tax_amount:.2f}\n"
                f"Total Final: ${order.total_amount:.2f}\n"
                f"Estado: {order.status}\n\n"
                f"Para confirmar y despachar: /confirmar_pedido {order.id} <ID_BODEGA>"
            )
        except Exception as e:
            return f"Error al generar cotizacion: {e}"

    @staticmethod
    def handle_confirmar_pedido(
        telegram_user_id: int,
        order_id: int,
        warehouse_id: int,
        session: Session,
    ) -> str:
        """Confirma la cotizacion y descuenta mercancia del inventario."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return "Acceso denegado. Primero debes vincular tu cuenta."

        if not AuthService.has_role(session, telegram_user_id, [UserRole.VENDEDOR.value, UserRole.GERENTE.value, UserRole.ADMIN.value]):
            return "Permiso denegado para confirmar pedidos."

        try:
            order = SalesOrderService.confirm_and_dispatch_order(
                session=session,
                order_id=order_id,
                warehouse_id=warehouse_id,
                user_id=user.id,
            )
            return (
                f"PEDIDO CONFIRMADO Y DESPACHADO EXITOSAMENTE\n"
                f"Numero: {order.order_number}\n"
                f"Cliente: {order.customer_name}\n"
                f"Total Despachado: ${order.total_amount:.2f}\n"
                f"Estado Actual: {order.status}\n"
                f"Stock descontado con asiento Kardex registrado."
            )
        except Exception as e:
            return f"Error al confirmar pedido: {e}"

    @staticmethod
    def handle_free_text(telegram_user_id: int, text: str, session: Session) -> str:
        """Enruta mensajes en lenguaje natural utilizando el clasificador de intenciones NLP."""
        intent, param = NLPService.parse_intent(text)

        if intent == NLPService.INTENT_STOCK:
            if param:
                return BotCommandHandler.handle_stock(telegram_user_id, param, session)
            return "Para consultar stock indica el nombre o SKU del producto."

        elif intent == NLPService.INTENT_CRITICAL_STOCK:
            return BotCommandHandler.handle_alertas(telegram_user_id, session)

        elif intent == NLPService.INTENT_PENDING_ORDERS:
            return BotCommandHandler.handle_ordenes_pendientes(telegram_user_id, session)

        elif intent == NLPService.INTENT_KARDEX:
            if param:
                return BotCommandHandler.handle_kardex(telegram_user_id, param, session)
            return "Para ver el Kardex indica el SKU del producto (ej: /kardex TAL-4402)."

        elif intent == NLPService.INTENT_SALES_QUOTE:
            if param:
                return f"Para cotizar '{param}' utiliza el comando formal: /pedido <NombreCliente> {param} <Cantidad>"
            return "Para emitir una cotizacion de venta escribe: /pedido <NombreCliente> <SKU> <Cantidad>"

        elif intent == NLPService.INTENT_REPORT:
            msg, _ = BotCommandHandler.handle_reporte(telegram_user_id, session)
            return msg

        elif intent == NLPService.INTENT_HELP:
            return BotCommandHandler.handle_start(telegram_user_id, session)

        return (
            f"No logre comprender con certeza tu mensaje: '{text}'.\n"
            "Puedes usar comandos directos como /stock, /kardex, /alertas, /ordenes, /pedido o /reporte."
        )
