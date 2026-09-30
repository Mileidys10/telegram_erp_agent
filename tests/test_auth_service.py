"""Pruebas unitarias de autenticacion, roles RBAC y vinculacion OTP."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import Base, UserRole
from src.services.auth_service import AuthService


class TestAuthService(unittest.TestCase):
    """Verifica generacion de OTP, vinculacion de Telegram y control de roles."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Registrar usuario corporativo inicial
        self.user = AuthService.register_user(
            session=self.session,
            username="vendedor_ana",
            full_name="Ana Vendedora",
            email="ana@empresa.com",
            role=UserRole.VENDEDOR.value,
        )
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_otp_generation_and_linking(self):
        otp = AuthService.generate_otp(self.session, "vendedor_ana")
        self.session.commit()

        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        # Vincular con ID de Telegram 998877
        linked_user = AuthService.link_telegram_user(self.session, telegram_user_id=998877, otp_code=otp)
        self.session.commit()

        self.assertEqual(linked_user.telegram_user_id, 998877)
        self.assertIsNone(linked_user.otp_code)

        # Consultar por Telegram ID
        found = AuthService.get_user_by_telegram_id(self.session, 998877)
        self.assertIsNotNone(found)
        self.assertEqual(found.username, "vendedor_ana")

    def test_invalid_otp_fails(self):
        with self.assertRaises(ValueError):
            AuthService.link_telegram_user(self.session, telegram_user_id=12345, otp_code="000000")

    def test_role_permissions_rbac(self):
        otp = AuthService.generate_otp(self.session, "vendedor_ana")
        AuthService.link_telegram_user(self.session, telegram_user_id=998877, otp_code=otp)
        self.session.commit()

        # Ana es VENDEDOR
        self.assertTrue(AuthService.has_role(self.session, 998877, [UserRole.VENDEDOR.value]))
        # Ana no tiene permisos de ALMACENERO ni GERENTE
        self.assertFalse(AuthService.has_role(self.session, 998877, [UserRole.GERENTE.value]))


if __name__ == "__main__":
    unittest.main()
