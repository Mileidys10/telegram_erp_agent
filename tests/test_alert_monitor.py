"""Pruebas unitarias para el monitor de alertas y stock critico."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import Base, Product, Stock, Warehouse
from src.services.alert_monitor import AlertMonitorDaemon


class TestAlertMonitor(unittest.TestCase):
    """Verifica la deteccion y emision de alertas de desabastecimiento."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        w = Warehouse(code="BOD-01", name="Bodega Monitoreo")
        # Producto con stock critico (5 <= 15)
        p1 = Product(
            sku="CRI-001",
            name="Articulo Critico",
            category="Fijaciones",
            cost_price=10.0,
            sale_price=20.0,
            stock_minimo=15.0,
        )
        # Producto con stock saludable (50 > 10)
        p2 = Product(
            sku="OK-002",
            name="Articulo Saludable",
            category="Herramientas",
            cost_price=30.0,
            sale_price=60.0,
            stock_minimo=10.0,
        )
        self.session.add_all([w, p1, p2])
        self.session.flush()

        s1 = Stock(product_id=p1.id, warehouse_id=w.id, quantity=5.0)
        s2 = Stock(product_id=p2.id, warehouse_id=w.id, quantity=50.0)
        self.session.add_all([s1, s2])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_inspect_critical_stock_identifies_deficits(self):
        """Verifica que el monitor identifica solo articulos en quiebre o deficit."""
        alerts = AlertMonitorDaemon.inspect_critical_stock(self.session)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sku"], "CRI-001")
        self.assertEqual(alert["current_stock"], 5.0)
        self.assertEqual(alert["stock_minimo"], 15.0)
        self.assertEqual(alert["deficit"], 10.0)


if __name__ == "__main__":
    unittest.main()
