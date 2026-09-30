"""Pruebas unitarias de compilacion de reportes PDF con ReportLab."""

import os
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import Base, Product, Stock, Warehouse
from src.services.report_service import ReportService


class TestReportService(unittest.TestCase):
    """Verifica generacion fisica de documentos PDF de inventario."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        w = Warehouse(code="BOD-01", name="Bodega Prueba")
        p = Product(
            sku="REP-001",
            name="Articulo Reporte",
            category="Pruebas",
            cost_price=10.0,
            sale_price=20.0,
            stock_minimo=5.0,
        )
        self.session.add_all([w, p])
        self.session.flush()

        s = Stock(product_id=p.id, warehouse_id=w.id, quantity=50.0)
        self.session.add(s)
        self.session.commit()

        self.test_pdf = os.path.join("reports", "test_report.pdf")
        self.kardex_pdf = os.path.join("reports", "test_kardex.pdf")

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        for f in (self.test_pdf, self.kardex_pdf):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_generate_pdf_file_created(self):
        result_path = ReportService.generate_inventory_valuation_pdf(
            session=self.session,
            output_filepath=self.test_pdf,
            company_name="Empresa Test S.A.",
            requested_by="QA Tester",
        )

        self.assertTrue(os.path.exists(result_path))
        self.assertGreater(os.path.getsize(result_path), 1000)

    def test_generate_kardex_pdf_file_created(self):
        """Verifica la compilacion del documento Kardex con trazabilidad contable."""
        result_path = ReportService.generate_kardex_pdf(
            session=self.session,
            product_sku="REP-001",
            output_filepath=self.kardex_pdf,
            company_name="Empresa Test S.A.",
            requested_by="QA Auditor",
        )

        self.assertTrue(os.path.exists(result_path))
        self.assertGreater(os.path.getsize(result_path), 1000)


if __name__ == "__main__":
    unittest.main()
