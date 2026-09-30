"""Pruebas unitarias del flujo de aprobacion y rechazo de ordenes de compra."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import Base, User, UserRole
from src.services.purchase_order_service import PurchaseOrderService


class TestPurchaseOrders(unittest.TestCase):
    """Verifica creacion, aprobacion directiva y rechazo de ordenes de compra."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        self.gerente = User(
            username="gerente_luis",
            full_name="Luis Gerente",
            email="luis@empresa.com",
            role=UserRole.GERENTE.value,
        )
        self.comprador = User(
            username="comprador_pedro",
            full_name="Pedro Compras",
            email="pedro@empresa.com",
            role=UserRole.ALMACENERO.value,
        )
        self.session.add_all([self.gerente, self.comprador])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_approve_purchase_order(self):
        order = PurchaseOrderService.create_order(
            session=self.session,
            order_number="OC-5001",
            supplier_name="Proveedor A",
            total_amount=2500.0,
            created_by_id=self.comprador.id,
        )
        self.session.commit()

        self.assertEqual(order.status, "PENDIENTE")

        approved = PurchaseOrderService.approve_order(
            session=self.session,
            order_id=order.id,
            approved_by_user_id=self.gerente.id,
            telegram_user_id=888,
        )
        self.session.commit()

        self.assertEqual(approved.status, "APROBADA")
        self.assertIsNotNone(approved.approved_at)

    def test_reject_purchase_order(self):
        order = PurchaseOrderService.create_order(
            session=self.session,
            order_number="OC-5002",
            supplier_name="Proveedor B",
            total_amount=15000.0,
            created_by_id=self.comprador.id,
        )
        self.session.commit()

        rejected = PurchaseOrderService.reject_order(
            session=self.session,
            order_id=order.id,
            rejected_by_user_id=self.gerente.id,
            reason="Excede presupuesto mensual autorizado",
            telegram_user_id=888,
        )
        self.session.commit()

        self.assertEqual(rejected.status, "RECHAZADA")
        self.assertEqual(rejected.rejection_reason, "Excede presupuesto mensual autorizado")

    def test_unauthorized_approval_fails(self):
        order = PurchaseOrderService.create_order(
            self.session, "OC-5003", "Proveedor C", 500.0, self.comprador.id
        )
        self.session.commit()

        # Comprador no tiene rol GERENTE o ADMIN
        with self.assertRaises(PermissionError):
            PurchaseOrderService.approve_order(self.session, order.id, self.comprador.id)


if __name__ == "__main__":
    unittest.main()
