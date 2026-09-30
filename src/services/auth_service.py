"""Servicio de autenticacion, vinculacion OTP y control de acceso RBAC."""

from datetime import datetime, timedelta, timezone
import random
from typing import List, Optional
from sqlalchemy.orm import Session

from ..domain.models import AuditLog, User, UserRole, utc_now


class AuthService:
    """Gestiona la identidad de usuarios corporativos en Telegram."""

    @staticmethod
    def register_user(
        session: Session,
        username: str,
        full_name: str,
        email: str,
        role: str = UserRole.VENDEDOR.value,
        telegram_user_id: Optional[int] = None,
    ) -> User:
        """Registra un nuevo usuario corporativo."""
        existing = session.query(User).filter(User.username == username.strip()).first()
        if existing:
            raise ValueError(f"El nombre de usuario '{username}' ya existe.")

        user = User(
            username=username.strip(),
            full_name=full_name.strip(),
            email=email.strip().lower(),
            role=role,
            telegram_user_id=telegram_user_id,
            is_active=True,
            created_at=utc_now(),
        )
        session.add(user)
        session.flush()
        return user

    @staticmethod
    def generate_otp(session: Session, username: str) -> str:
        """Genera un codigo OTP de 6 digitos con validez de 10 minutos para vinculacion."""
        user = session.query(User).filter(User.username == username.strip()).first()
        if not user:
            raise ValueError(f"No existe el usuario corporativo '{username}'.")

        otp = f"{random.randint(100000, 999999)}"
        user.otp_code = otp
        user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        session.flush()
        return otp

    @staticmethod
    def link_telegram_user(session: Session, telegram_user_id: int, otp_code: str) -> User:
        """Valida el codigo OTP y vincula el ID de Telegram a la cuenta corporativa."""
        clean_otp = otp_code.strip()
        user = session.query(User).filter(User.otp_code == clean_otp).first()

        if not user:
            raise ValueError("Codigo OTP no valido.")

        now_utc = datetime.now(timezone.utc)
        expires_at = user.otp_expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if not expires_at or now_utc > expires_at:
            raise ValueError("El codigo OTP ha expirado. Solicite un nuevo codigo desde el portal.")

        prev_user = session.query(User).filter(User.telegram_user_id == telegram_user_id).first()
        if prev_user and prev_user.id != user.id:
            prev_user.telegram_user_id = None

        user.telegram_user_id = telegram_user_id
        user.otp_code = None
        user.otp_expires_at = None

        audit = AuditLog(
            telegram_user_id=telegram_user_id,
            action="LINK_TELEGRAM_USER",
            details=f"Usuario corporativo '{user.username}' vinculado a Telegram ID: {telegram_user_id}",
            timestamp=utc_now(),
        )
        session.add(audit)
        session.flush()
        return user

    @staticmethod
    def get_user_by_telegram_id(session: Session, telegram_user_id: int) -> Optional[User]:
        """Obtiene la ficha del usuario vinculado a un ID numerico de Telegram."""
        return session.query(User).filter(User.telegram_user_id == telegram_user_id, User.is_active == True).first()

    @staticmethod
    def has_role(session: Session, telegram_user_id: int, allowed_roles: List[str]) -> bool:
        """Valida si el usuario de Telegram posee alguno de los roles autorizados."""
        user = AuthService.get_user_by_telegram_id(session, telegram_user_id)
        if not user:
            return False
        if user.role == UserRole.ADMIN.value:
            return True
        return user.role in allowed_roles
