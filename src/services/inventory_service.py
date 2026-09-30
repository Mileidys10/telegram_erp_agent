"""Servicio transaccional de inventario y Kardex para ERP."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain.models import AuditLog, KardexMovement, Product, Stock, Warehouse, utc_now


class InventoryService:
    """Gestiona operaciones de stock, movimientos de inventario y consultas de Kardex."""

    @staticmethod
    def get_product_by_sku(session: Session, sku: str) -> Optional[Product]:
        """Obtiene un producto por su SKU exacto."""
        return session.query(Product).filter(func.upper(Product.sku) == sku.strip().upper()).first()

    @staticmethod
    def search_products(session: Session, query_text: str, limit: int = 10) -> List[Product]:
        """Busca productos por SKU, nombre o categoria."""
        term = f"%{query_text.strip()}%"
        return (
            session.query(Product)
            .filter((Product.sku.ilike(term)) | (Product.name.ilike(term)) | (Product.category.ilike(term)))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_product_stock_summary(session: Session, sku: str) -> Optional[Dict]:
        """Calcula el stock total disponible y por almacen para un SKU."""
        product = InventoryService.get_product_by_sku(session, sku)
        if not product:
            return None

        stocks = session.query(Stock).filter(Stock.product_id == product.id).all()
        total_qty = sum(s.quantity for s in stocks)
        total_reserved = sum(s.reserved_quantity for s in stocks)
        available = max(0.0, total_qty - total_reserved)

        warehouse_breakdown = [
            {
                "warehouse_id": s.warehouse_id,
                "warehouse_code": s.warehouse.code if s.warehouse else "N/A",
                "warehouse_name": s.warehouse.name if s.warehouse else "N/A",
                "quantity": s.quantity,
                "reserved": s.reserved_quantity,
                "available": s.available_quantity,
            }
            for s in stocks
        ]

        return {
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "unit_measure": product.unit_measure,
            "cost_price": product.cost_price,
            "sale_price": product.sale_price,
            "stock_minimo": product.stock_minimo,
            "total_quantity": total_qty,
            "total_reserved": total_reserved,
            "available_quantity": available,
            "is_critical": total_qty <= product.stock_minimo,
            "warehouses": warehouse_breakdown,
        }

    @staticmethod
    def record_movement(
        session: Session,
        sku: str,
        warehouse_id: int,
        movement_type: str,
        quantity: float,
        unit_cost: float,
        reference: str,
        user_id: int,
        telegram_user_id: Optional[int] = None,
    ) -> Tuple[KardexMovement, float]:
        """Ejecuta un asiento transaccional ACID de Kardex y actualiza el stock fisico."""
        if quantity <= 0:
            raise ValueError("La cantidad del movimiento debe ser estrictamente positiva.")

        product = InventoryService.get_product_by_sku(session, sku)
        if not product:
            raise ValueError(f"No existe ningun producto con el SKU '{sku}'.")

        warehouse = session.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not warehouse:
            raise ValueError(f"No existe ningun almacen con el ID {warehouse_id}.")

        mov_type = movement_type.upper().strip()
        if mov_type not in ("ENTRADA", "SALIDA", "TRASLADO"):
            raise ValueError(f"Tipo de movimiento '{mov_type}' no valido. Usar ENTRADA, SALIDA o TRASLADO.")

        # Obtener o inicializar registro de stock en dicho almacen
        stock_record = (
            session.query(Stock)
            .filter(Stock.product_id == product.id, Stock.warehouse_id == warehouse.id)
            .first()
        )
        if not stock_record:
            stock_record = Stock(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=0.0,
                reserved_quantity=0.0,
            )
            session.add(stock_record)
            session.flush()

        current_qty = stock_record.quantity

        if mov_type in ("SALIDA", "TRASLADO"):
            if current_qty < quantity:
                raise ValueError(
                    f"Stock insuficiente en '{warehouse.name}'. Stock actual: {current_qty}, requerido: {quantity}."
                )
            new_qty = current_qty - quantity
        else:  # ENTRADA
            new_qty = current_qty + quantity

        stock_record.quantity = new_qty

        # Calcular balance total entre todos los almacenes
        all_stocks = session.query(Stock).filter(Stock.product_id == product.id).all()
        balance_total = sum(s.quantity for s in all_stocks)

        total_cost = quantity * unit_cost
        movement = KardexMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type=mov_type,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            balance_quantity=balance_total,
            reference=reference,
            user_id=user_id,
            timestamp=utc_now(),
        )
        session.add(movement)

        # Registro en bitacora de auditoria
        audit = AuditLog(
            telegram_user_id=telegram_user_id,
            action=f"KARDEX_{mov_type}",
            details=f"SKU: {sku} | Cantidad: {quantity} | Almacen: {warehouse.code} | Saldo: {balance_total}",
            timestamp=utc_now(),
        )
        session.add(audit)
        session.flush()

        return movement, balance_total

    @staticmethod
    def get_kardex_history(session: Session, sku: str, limit: int = 10) -> List[Dict]:
        """Recupera los asientos mas recientes del Kardex para un producto."""
        product = InventoryService.get_product_by_sku(session, sku)
        if not product:
            return []

        movements = (
            session.query(KardexMovement)
            .filter(KardexMovement.product_id == product.id)
            .order_by(KardexMovement.timestamp.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": m.id,
                "timestamp": m.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "movement_type": m.movement_type,
                "quantity": m.quantity,
                "unit_cost": m.unit_cost,
                "total_cost": m.total_cost,
                "balance": m.balance_quantity,
                "reference": m.reference,
                "warehouse_code": m.warehouse.code if m.warehouse else "N/A",
                "user_name": m.user.full_name if m.user else "Sistema",
            }
            for m in movements
        ]

    @staticmethod
    def get_critical_stock_items(session: Session) -> List[Dict]:
        """Identifica todos los productos cuyo stock global total este en o por debajo del stock minimo."""
        products = session.query(Product).all()
        critical_items = []

        for p in products:
            stocks = session.query(Stock).filter(Stock.product_id == p.id).all()
            total_stock = sum(s.quantity for s in stocks)
            if total_stock <= p.stock_minimo:
                critical_items.append({
                    "sku": p.sku,
                    "name": p.name,
                    "category": p.category,
                    "current_stock": total_stock,
                    "stock_minimo": p.stock_minimo,
                    "unit_measure": p.unit_measure,
                    "deficit": max(0.0, p.stock_minimo - total_stock),
                })

        return critical_items
