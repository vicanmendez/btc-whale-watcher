"""Módulo de pre-registro inmutable de predicciones (RF-10, RF-14, Principio IX).

Garantiza que toda predicción se registre con marca temporal inmutable con anterioridad
a la ocurrencia del desenlace evaluado.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..base_datos.modelos import CaracteristicaCalculadaORM, EventoAnalizadoORM, PrediccionORM
from ..tiempo import DURACION_HORIZONTE, a_utc, ahora_utc
from .motor_impacto import EstimacionHorizonte, MotorImpacto

registro = logging.getLogger(__name__)


def calcular_hash_prediccion(
    evento_id: int, horizonte: str, t_ref: str, datos_json: str
) -> str:
    cadena = f"{evento_id}|{horizonte}|{t_ref}|{datos_json}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


class ServicioPrerregistro:
    def __init__(self, sesion: Session, motor_impacto: MotorImpacto) -> None:
        self.sesion = sesion
        self.motor = motor_impacto

    def prerregistrar_evento(
        self, evento: EventoAnalizadoORM, caracteristica: CaracteristicaCalculadaORM
    ) -> Sequence[PrediccionORM]:
        """Genera y persiste las predicciones para los 3 horizontes de forma inmutable."""
        estimaciones = self.motor.generar_estimaciones(evento, caracteristica)
        t_ref = a_utc(evento.marca_tiempo_referencia)
        predicciones_creadas: list[PrediccionORM] = []

        datos_snapshot = {
            "evento_id": evento.id,
            "txid": evento.transaccion.txid if evento.transaccion else None,
            "monto_btc": evento.monto_relevante_btc,
            "categoria": evento.categoria_movimiento,
            "precio_referencia": caracteristica.precio_referencia_usd,
            "volumen_24h_btc": caracteristica.volumen_24h_btc,
            "variacion_24h_pct": caracteristica.variacion_precio_24h_pct,
            "volatilidad_7d": caracteristica.volatilidad_historica_7d,
        }
        snapshot_json = json.dumps(datos_snapshot, sort_keys=True, default=str)

        for est in estimaciones:
            # Comprobar si ya existe
            consulta = select(PrediccionORM).where(
                PrediccionORM.evento_id == evento.id,
                PrediccionORM.horizonte == est.horizonte,
            )
            existente = self.sesion.scalars(consulta).first()
            if existente is not None:
                predicciones_creadas.append(existente)
                continue

            duracion = DURACION_HORIZONTE[est.horizonte]
            vencimiento = t_ref + duracion
            hash_c = calcular_hash_prediccion(evento.id, est.horizonte, t_ref.isoformat(), snapshot_json)

            prediccion = PrediccionORM(
                evento_id=evento.id,
                horizonte=est.horizonte,
                tipo_estimacion=est.tipo_estimacion,
                marca_tiempo_referencia=t_ref,
                marca_tiempo_registro=ahora_utc(),
                fecha_vencimiento_utc=vencimiento,
                precio_inicial_usd=caracteristica.precio_referencia_usd,
                umbral_neutral_pct=self.motor.config.umbral_neutral_pct(est.horizonte),
                probabilidad_alcista=est.probabilidad_alcista,
                probabilidad_bajista=est.probabilidad_bajista,
                probabilidad_neutral=est.probabilidad_neutral,
                retorno_esperado_pct=est.retorno_esperado_pct,
                rango_incertidumbre_inferior=est.rango_incertidumbre_inferior,
                rango_incertidumbre_superior=est.rango_incertidumbre_superior,
                razon_indeterminacion=est.razon_indeterminacion,
                evidencia=est.evidencia,
                limitaciones=est.limitaciones,
                modelo_version=est.modelo_version,
                datos_entrada_json=snapshot_json,
                hash_contenido=hash_c,
            )
            self.sesion.add(prediccion)
            predicciones_creadas.append(prediccion)

        evento.estado_procesamiento = "ANALIZADO"
        self.sesion.flush()
        return predicciones_creadas
