"""Fixtures compartidas: base de datos en memoria y configuración de prueba."""

from __future__ import annotations

import pytest

from btc_whale_intelligence.base_datos.conexion import crear_fabrica_sesiones, crear_motor
from btc_whale_intelligence.base_datos.inicializador import inicializar_base_datos
from btc_whale_intelligence.configuracion import cargar_configuracion


@pytest.fixture
def motor():
    motor = crear_motor("sqlite:///:memory:")
    inicializar_base_datos(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def fabrica(motor):
    return crear_fabrica_sesiones(motor)


@pytest.fixture
def sesion(fabrica):
    s = fabrica()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def config():
    return cargar_configuracion(
        entorno={
            "DATABASE_URL": "sqlite:///:memory:",
            "LOG_FILE": "",
            "SMTP_HOST": "smtp.prueba.local",
            "SMTP_FROM": "bot@prueba.local",
            "ALERT_EMAIL_TO": "inversor@prueba.local",
            "SMTP_PASSWORD": "clave-de-prueba",
            "ESPLORA_FALLBACK_URL": "",
        }
    )
