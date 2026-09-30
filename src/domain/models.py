"""Modelos de dominio relacional del ERP con SQLAlchemy."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    """Genera la marca temporal actual en UTC timezone-aware."""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    """Roles de acceso y permisos RBAC en el sistema."""
    ADMIN = "ADMIN"
    GERENTE = "GERENTE"
    ALMACENERO = "ALMACENERO"
    VENDEDOR = "VENDEDOR"


class User(Base):
    """Usuario corporativo con vinculacion a Telegram."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(String(20), default=UserRole.VENDEDOR.value, nullable=False)
    telegram_user_id = Column(Integer, unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    otp_code = Column(String(10), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    kardex_movements = relationship("KardexMovement", back_populates="user")


class Warehouse(Base):
    """Almacen o bodega fisica de almacenamiento."""
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(150), nullable=True)

    stocks = relationship("Stock", back_populates="warehouse")
    kardex_movements = relationship("KardexMovement", back_populates="warehouse")


class Product(Base):
    """Articulo o producto en el catalogo maestro del ERP."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    unit_measure = Column(String(10), default="UND", nullable=False)
    cost_price = Column(Float, default=0.0, nullable=False)
    sale_price = Column(Float, default=0.0, nullable=False)
    stock_minimo = Column(Float, default=10.0, nullable=False)

    stocks = relationship("Stock", back_populates="product")
    kardex_movements = relationship("KardexMovement", back_populates="product")


class Stock(Base):
    """Existencia fisica y comprometida de un producto en un almacen especifico."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    quantity = Column(Float, default=0.0, nullable=False)
    reserved_quantity = Column(Float, default=0.0, nullable=False)

    product = relationship("Product", back_populates="stocks")
    warehouse = relationship("Warehouse", back_populates="stocks")

    @property
    def available_quantity(self) -> float:
        """Cantidad neta disponible para venta o despacho."""
        return max(0.0, self.quantity - self.reserved_quantity)


class KardexMovement(Base):
    """Asiento inmutable de transaccion de inventario para trazabilidad contable."""
    __tablename__ = "kardex_movements"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    balance_quantity = Column(Float, nullable=False)
    reference = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    product = relationship("Product", back_populates="kardex_movements")
    warehouse = relationship("Warehouse", back_populates="kardex_movements")
    user = relationship("User", back_populates="kardex_movements")


class PurchaseOrder(Base):
    """Orden de compra sujeta a aprobacion directiva."""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(30), unique=True, nullable=False, index=True)
    supplier_name = Column(String(150), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(25), default="PENDIENTE", nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    approved_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Bitacora de auditoria de acciones realizadas via Telegram."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utc_now, nullable=False)


class SalesOrderStatus(str, Enum):
    """Estados del ciclo de vida de un pedido de venta."""
    COTIZACION = "COTIZACION"
    CONFIRMADO = "CONFIRMADO"
    DESPACHADO = "DESPACHADO"
    CANCELADO = "CANCELADO"


class SalesOrder(Base):
    """Pedido o cotizacion de venta emitida a un cliente."""
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(30), unique=True, nullable=False, index=True)
    customer_name = Column(String(150), nullable=False)
    customer_tax_id = Column(String(30), nullable=True)
    subtotal_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(25), default=SalesOrderStatus.COTIZACION.value, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)

    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
    created_by = relationship("User")


class SalesOrderItem(Base):
    """Linea de item de un pedido de venta."""
    __tablename__ = "sales_order_items"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    sales_order = relationship("SalesOrder", back_populates="items")
    product = relationship("Product")
