"""Motor SQLAlchemy sobre SQLite en modo WAL y gestión de sesiones."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def crear_motor(url: str) -> Engine:
    """Crea el motor. Para SQLite activa WAL, claves foráneas y busy_timeout."""
    es_sqlite = url.startswith("sqlite")
    en_memoria = es_sqlite and (url in {"sqlite://", "sqlite:///:memory:"} or ":memory:" in url)

    opciones: dict = {"future": True}
    if es_sqlite:
        opciones["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if en_memoria:
            opciones["poolclass"] = StaticPool
        else:
            ruta = url.split("sqlite:///", 1)[-1]
            if ruta:
                Path(ruta).parent.mkdir(parents=True, exist_ok=True)

    motor = create_engine(url, **opciones)

    if es_sqlite:

        @event.listens_for(motor, "connect")
        def _pragmas(conexion_dbapi, _registro):  # pragma: no cover - trivial
            cursor = conexion_dbapi.cursor()
            if not en_memoria:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return motor


def crear_fabrica_sesiones(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=motor, expire_on_commit=False, future=True)


@contextmanager
def sesion_transaccional(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    """Abre una sesión, hace commit al salir y rollback ante cualquier excepción."""
    sesion = fabrica()
    try:
        yield sesion
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    finally:
        sesion.close()
