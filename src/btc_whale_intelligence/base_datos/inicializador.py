"""Inicialización del esquema y utilidades operativas (estado de ingesta y errores)."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from ..tiempo import ahora_utc
from .modelos import Base, ErrorOperativoORM, EstadoIngestaORM

registro = logging.getLogger(__name__)


def inicializar_base_datos(motor: Engine) -> list[str]:
    """Crea las tablas que falten (idempotente). Devuelve la lista de tablas existentes."""
    Base.metadata.create_all(motor)
    return sorted(inspect(motor).get_table_names())


def obtener_estado_ingesta(sesion: Session, fuente: str) -> EstadoIngestaORM:
    estado = sesion.get(EstadoIngestaORM, fuente)
    if estado is None:
        estado = EstadoIngestaORM(fuente=fuente, ultimo_bloque_procesado=0, conteo_errores_consecutivos=0)
        sesion.add(estado)
        sesion.flush()
    return estado


def registrar_exito_ingesta(sesion: Session, fuente: str) -> None:
    estado = obtener_estado_ingesta(sesion, fuente)
    estado.ultima_sincronizacion_utc = ahora_utc()
    estado.conteo_errores_consecutivos = 0


def registrar_error(
    sesion: Session,
    componente: str,
    error: BaseException | str,
    contexto: Optional[dict[str, Any]] = None,
    fuente_ingesta: Optional[str] = None,
) -> None:
    """Persiste un error operativo sin propagar fallos secundarios."""
    tipo = type(error).__name__ if isinstance(error, BaseException) else "Aviso"
    mensaje = str(error)[:2000]
    sesion.add(
        ErrorOperativoORM(
            componente=componente,
            tipo_error=tipo,
            mensaje=mensaje,
            contexto=json.dumps(contexto, default=str, ensure_ascii=False) if contexto else None,
        )
    )
    if fuente_ingesta:
        estado = obtener_estado_ingesta(sesion, fuente_ingesta)
        estado.conteo_errores_consecutivos += 1
        estado.ultimo_error = mensaje
    registro.warning("[%s] %s: %s", componente, tipo, mensaje)
