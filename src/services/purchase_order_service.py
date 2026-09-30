"""Servicio de ordenes de compra y aprobaciones directivas."""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from ..domain.models import AuditLog, PurchaseOrder, User, UserRole, utc_now


class PurchaseOrderService:
    """Gestiona el ciclo de vida de ordenes de compra desde Telegram."""

    @staticmethod
    def create_order(
        session: Session,
        order_number: str,
        supplier_name: str,
        total_amount: float,
        created_by_id: int,
    ) -> PurchaseOrder:
        """Crea una orden de compra en estado PENDIENTE."""
        order = PurchaseOrder(
            order_number=order_number.strip().upper(),
            supplier_name=supplier_name.strip(),
            total_amount=total_amount,
            status="PENDIENTE",
            created_by_id=created_by_id,
            created_at=utc_now(),
        )
        session.add(order)
        session.flush()
        return order

    @staticmethod
    def get_pending_orders(session: Session) -> List[Dict]:
        """Obtiene todas las ordenes que requieren aprobacion directiva."""
        orders = (
            session.query(PurchaseOrder)
            .filter(PurchaseOrder.status == "PENDIENTE")
            .order_by(PurchaseOrder.created_at.asc())
            .all()
        )
        return [
            {
                "id": o.id,
                "order_number": o.order_number,
                "supplier_name": o.supplier_name,
                "total_amount": o.total_amount,
                "status": o.status,
                "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for o in orders
        ]

    @staticmethod
    def approve_order(
        session: Session,
        order_id: int,
        approved_by_user_id: int,
        telegram_user_id: Optional[int] = None,
    ) -> PurchaseOrder:
        """Aprueba formalmente una orden de compra."""
        order = session.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
        if not order:
            raise ValueError(f"No existe la orden de compra con ID {order_id}.")

        if order.status != "PENDIENTE":
            raise ValueError(f"La orden {order.order_number} ya se encuentra en estado '{order.status}'.")

        approver = session.query(User).filter(User.id == approved_by_user_id).first()
        if not approver or approver.role not in (UserRole.GERENTE.value, UserRole.ADMIN.value):
            raise PermissionError("Solo un usuario con rol GERENTE o ADMIN puede aprobar ordenes de compra.")

        order.status = "APROBADA"
        order.approved_by_id = approver.id
        order.approved_at = utc_now()

        audit = AuditLog(
            telegram_user_id=telegram_user_id,
            action="APROBAR_ORDEN_COMPRA",
            details=f"Orden: {order.order_number} | Aprobador: {approver.username} | Total: {order.total_amount}",
            timestamp=utc_now(),
        )
        session.add(audit)
        session.flush()
        return order

    @staticmethod
    def reject_order(
        session: Session,
        order_id: int,
        rejected_by_user_id: int,
        reason: str,
        telegram_user_id: Optional[int] = None,
    ) -> PurchaseOrder:
        """Rechaza una orden de compra registrando el motivo."""
        order = session.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
        if not order:
            raise ValueError(f"No existe la orden de compra con ID {order_id}.")

        if order.status != "PENDIENTE":
            raise ValueError(f"La orden {order.order_number} ya se encuentra en estado '{order.status}'.")

        rejector = session.query(User).filter(User.id == rejected_by_user_id).first()
        if not rejector or rejector.role not in (UserRole.GERENTE.value, UserRole.ADMIN.value):
            raise PermissionError("Solo un usuario con rol GERENTE o ADMIN puede rechazar ordenes de compra.")

        order.status = "RECHAZADA"
        order.approved_by_id = rejector.id
        order.approved_at = utc_now()
        order.rejection_reason = reason.strip()

        audit = AuditLog(
            telegram_user_id=telegram_user_id,
            action="RECHAZAR_ORDEN_COMPRA",
            details=f"Orden: {order.order_number} | Rechazador: {rejector.username} | Motivo: {reason}",
            timestamp=utc_now(),
        )
        session.add(audit)
        session.flush()
        return order
