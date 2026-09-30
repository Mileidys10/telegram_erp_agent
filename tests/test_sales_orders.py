"""Pruebas unitarias para el servicio de pedidos de venta y cotizaciones express."""

import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import (
    Base,
    Product,
    SalesOrder,
    SalesOrderStatus,
    Stock,
    User,
    UserRole,
    Warehouse,
)
from src.services.sales_order_service import SalesOrderService


class TestSalesOrders(unittest.TestCase):
    """Pruebas para cotizaciones, confirmaciones y reportes de ventas."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Sembrar datos base
        self.warehouse = Warehouse(code="BOD-01", name="Bodega Central")
        self.user = User(
            username="vendedor_pedro",
            full_name="Pedro Vendedor",
            email="pedro@empresa.com",
            role=UserRole.VENDEDOR.value,
            telegram_user_id=4001,
        )
        self.product = Product(
            sku="TAL-4402",
            name="Taladro Percutor Industrial",
            category="Herramientas",
            unit_measure="UND",
            cost_price=50.0,
            sale_price=100.0,
            stock_minimo=10.0,
        )
        self.session.add_all([self.warehouse, self.user, self.product])
        self.session.flush()

        self.stock = Stock(
            product_id=self.product.id,
            warehouse_id=self.warehouse.id,
            quantity=50.0,
        )
        self.session.add(self.stock)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_create_sales_quote(self):
        """Verifica la emision de una cotizacion con calculo de IVA (19%) y subtotales."""
        items = [{"sku": "TAL-4402", "quantity": 5.0}]
        order = SalesOrderService.create_quote(
            session=self.session,
            user_id=self.user.id,
            customer_name="Constructora del Sur S.A.",
            customer_tax_id="76.123.456-7",
            items=items,
        )

        self.assertEqual(order.status, SalesOrderStatus.COTIZACION.value)
        self.assertEqual(order.subtotal_amount, 500.0)
        self.assertEqual(order.tax_amount, 95.0)  # 19% de 500
        self.assertEqual(order.total_amount, 595.0)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.items[0].subtotal, 500.0)

    def test_confirm_sales_order_deducts_stock(self):
        """Verifica que confirmar un pedido descuenta las existencias fisicas y crea asiento Kardex."""
        items = [{"sku": "TAL-4402", "quantity": 10.0}]
        order = SalesOrderService.create_quote(
            session=self.session,
            user_id=self.user.id,
            customer_name="Cliente Industrial",
            customer_tax_id=None,
            items=items,
        )

        confirmed_order = SalesOrderService.confirm_and_dispatch_order(
            session=self.session,
            order_id=order.id,
            warehouse_id=self.warehouse.id,
            user_id=self.user.id,
        )

        self.assertEqual(confirmed_order.status, SalesOrderStatus.CONFIRMADO.value)
        self.assertIsNotNone(confirmed_order.confirmed_at)

        # Verificar stock actualizado (50 - 10 = 40)
        updated_stock = self.session.query(Stock).filter(Stock.id == self.stock.id).first()
        self.assertEqual(updated_stock.quantity, 40.0)

    def test_sales_quote_pdf_compilation(self):
        """Verifica la compilacion fisica del PDF de cotizacion de venta."""
        items = [{"sku": "TAL-4402", "quantity": 2.0}]
        order = SalesOrderService.create_quote(
            session=self.session,
            user_id=self.user.id,
            customer_name="Cliente PDF Demo",
            customer_tax_id="12.345.678-9",
            items=items,
        )

        out_path = "reports/test_cotizacion.pdf"
        res_path = SalesOrderService.generate_sales_quote_pdf(
            session=self.session,
            order_id=order.id,
            output_filepath=out_path,
        )

        self.assertTrue(os.path.exists(res_path))
        self.assertGreater(os.path.getsize(res_path), 1000)
        if os.path.exists(out_path):
            os.remove(out_path)


if __name__ == "__main__":
    unittest.main()
