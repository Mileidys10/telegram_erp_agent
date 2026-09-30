"""Gestion de conexiones y sesiones de base de datos relacional."""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..domain.models import Base

DEFAULT_DB_URL = "sqlite:///erp_inventory.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None) -> None:
    """Crea todas las tablas del esquema en la base de datos."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


@contextmanager
def get_session(custom_engine=None) -> Generator[Session, None, None]:
    """Context manager para transacciones de base de datos seguras y aisladas."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=custom_engine or engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
