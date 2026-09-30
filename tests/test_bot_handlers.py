"""Pruebas unitarias de procesador de comandos y enrutador NLP de Telegram."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.bot.handlers import BotCommandHandler
from src.domain.models import Base, Product, PurchaseOrder, Stock, User, UserRole, Warehouse
from src.services.auth_service import AuthService
from src.services.nlp_service import NLPService


class TestBotHandlers(unittest.TestCase):
    """Verifica respuestas a comandos /start, /stock, /alertas, /ordenes y mensajes libres."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Sembrar datos
        self.warehouse = Warehouse(code="BOD-01", name="Bodega Central")
        self.admin = User(
            username="admin_user",
            full_name="Admin Test",
            email="admin@test.com",
            role=UserRole.ADMIN.value,
            telegram_user_id=1111,
            is_active=True,
        )
        self.gerente = User(
            username="gerente_user",
            full_name="Gerente Test",
            email="gerente@test.com",
            role=UserRole.GERENTE.value,
            telegram_user_id=2222,
            is_active=True,
        )
        self.product = Product(
            sku="TAL-4402",
            name="Taladro Percutor 850W",
            category="Herramientas",
            cost_price=40.0,
            sale_price=80.0,
            stock_minimo=15.0,
        )
        self.session.add_all([self.warehouse, self.admin, self.gerente, self.product])
        self.session.flush()

        self.stock = Stock(product_id=self.product.id, warehouse_id=self.warehouse.id, quantity=10.0)
        self.session.add(self.stock)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_start_unlinked_user(self):
        # Usuario desconocido (ID 9999)
        msg = BotCommandHandler.handle_start(9999, self.session)
        self.assertIn("Tu cuenta de Telegram aun no esta vinculada", msg)

    def test_start_linked_user(self):
        # Admin vinculado (ID 1111)
        msg = BotCommandHandler.handle_start(1111, self.session)
        self.assertIn("Bienvenido de nuevo, Admin Test", msg)
        self.assertIn("ADMIN", msg)

    def test_stock_exact_query(self):
        msg = BotCommandHandler.handle_stock(1111, "TAL-4402", self.session)
        self.assertIn("FICHA DE INVENTARIO: TAL-4402", msg)
        self.assertIn("Taladro Percutor 850W", msg)
        self.assertIn("ALERTA: STOCK CRITICO", msg)

    def test_alertas_critical_stock(self):
        msg = BotCommandHandler.handle_alertas(1111, self.session)
        self.assertIn("ALERTAS DE STOCK CRITICO", msg)
        self.assertIn("TAL-4402", msg)

    def test_free_text_nlp_routing(self):
        # Consulta en lenguaje natural
        msg = BotCommandHandler.handle_free_text(1111, "cuanto nos queda de taladro", self.session)
        self.assertIn("Taladro Percutor 850W", msg)

        # Consulta de alertas
        msg_alert = BotCommandHandler.handle_free_text(1111, "productos en quiebre de stock", self.session)
        self.assertIn("ALERTAS DE STOCK CRITICO", msg_alert)

        # Consulta de cotizacion
        msg_cot = BotCommandHandler.handle_free_text(1111, "cotizar taladro para cliente Juan", self.session)
        self.assertIn("/pedido", msg_cot)

    def test_pedido_handler_success(self):
        msg = BotCommandHandler.handle_pedido(
            telegram_user_id=1111,
            customer_name="Ferreteria Central",
            sku="TAL-4402",
            quantity=3.0,
            session=self.session,
        )
        self.assertIn("COTIZACION DE VENTA EMITIDA", msg)
        self.assertIn("Ferreteria Central", msg)
        self.assertIn("Total Final: $285.60", msg)  # 3 * 80 = 240 + 19% IVA (45.60) = 285.60

    def test_reporte_kardex_handler(self):
        msg, filepath = BotCommandHandler.handle_reporte_kardex(1111, "TAL-4402", self.session)
        self.assertIn("TAL-4402", msg)
        self.assertIsNotNone(filepath)
        import os
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


if __name__ == "__main__":
    unittest.main()
