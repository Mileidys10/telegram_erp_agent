"""Pruebas unitarias del modelo de dominio y transacciones de Kardex."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import Base, Product, Stock, User, UserRole, Warehouse
from src.services.inventory_service import InventoryService


class TestDomainAndDatabase(unittest.TestCase):
    """Verifica integridad referencial, transacciones ACID y Kardex."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Sembrar datos base
        self.warehouse = Warehouse(code="W01", name="Almacen Central")
        self.user = User(
            username="operador",
            full_name="Operador Test",
            email="op@empresa.com",
            role=UserRole.ALMACENERO.value,
        )
        self.product = Product(
            sku="SKU-100",
            name="Taladro Test",
            category="Herramientas",
            cost_price=50.0,
            sale_price=80.0,
            stock_minimo=10.0,
        )
        self.session.add_all([self.warehouse, self.user, self.product])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_record_movement_entrada(self):
        mov, new_balance = InventoryService.record_movement(
            session=self.session,
            sku="SKU-100",
            warehouse_id=self.warehouse.id,
            movement_type="ENTRADA",
            quantity=20.0,
            unit_cost=50.0,
            reference="Compra Factura F-001",
            user_id=self.user.id,
        )
        self.session.commit()

        self.assertEqual(mov.movement_type, "ENTRADA")
        self.assertEqual(new_balance, 20.0)
        self.assertEqual(mov.total_cost, 1000.0)

        # Verificar resumen de stock
        summary = InventoryService.get_product_stock_summary(self.session, "SKU-100")
        self.assertEqual(summary["total_quantity"], 20.0)
        self.assertEqual(summary["available_quantity"], 20.0)
        self.assertFalse(summary["is_critical"])

    def test_record_movement_salida_insuficiente(self):
        # Intentar sacar stock sin existencias debe lanzar ValueError
        with self.assertRaises(ValueError):
            InventoryService.record_movement(
                session=self.session,
                sku="SKU-100",
                warehouse_id=self.warehouse.id,
                movement_type="SALIDA",
                quantity=10.0,
                unit_cost=50.0,
                reference="Despacho Invalido",
                user_id=self.user.id,
            )

    def test_kardex_history_tracking(self):
        # Entrada de 30 unidades
        InventoryService.record_movement(
            self.session, "SKU-100", self.warehouse.id, "ENTRADA", 30.0, 50.0, "Ref-1", self.user.id
        )
        # Salida de 12 unidades
        InventoryService.record_movement(
            self.session, "SKU-100", self.warehouse.id, "SALIDA", 12.0, 50.0, "Ref-2", self.user.id
        )
        self.session.commit()

        history = InventoryService.get_kardex_history(self.session, "SKU-100")
        self.assertEqual(len(history), 2)
        # El mas reciente primero (SALIDA)
        self.assertEqual(history[0]["movement_type"], "SALIDA")
        self.assertEqual(history[0]["balance"], 18.0)


if __name__ == "__main__":
    unittest.main()
