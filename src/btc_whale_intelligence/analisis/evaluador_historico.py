"""Evaluador retrospectivo de predicciones frente a la realidad y baselines (RF-10, Principio VIII).

Compara obligatoriamente contra:
1. Baseline pasivo: Buy & Hold (mantener BTC).
2. Baseline ingenuo: Persistencia / Caminata aleatoria (retorno esperado = 0%).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..base_datos.modelos import PrediccionORM, ResultadoPrediccionORM
from ..configuracion import Configuracion
from ..mercado.sincronizador_mercado import SincronizadorMercado
from ..tiempo import a_utc, ahora_utc

registro = logging.getLogger(__name__)


def calcular_brier_score(
    p_alcista: float, p_bajista: float, p_neutral: float, resultado_categoria: str
) -> float:
    """Calcula la puntuación Brier multiclase (suma de errores cuadráticos)."""
    y_alcista = 1.0 if resultado_categoria == "ALCISTA" else 0.0
    y_bajista = 1.0 if resultado_categoria == "BAJISTA" else 0.0
    y_neutral = 1.0 if resultado_categoria == "NEUTRAL" else 0.0

    return (
        (p_alcista - y_alcista) ** 2
        + (p_bajista - y_bajista) ** 2
        + (p_neutral - y_neutral) ** 2
    )


class EvaluadorHistorico:
    def __init__(
        self, sesion: Session, config: Configuracion, sincronizador_mercado: SincronizadorMercado
    ) -> None:
        self.sesion = sesion
        self.config = config
        self.sincronizador = sincronizador_mercado

    def evaluar_predicciones_vencidas(
        self, ahora: Optional[datetime] = None
    ) -> Sequence[ResultadoPrediccionORM]:
        """Localiza predicciones cuyo horizonte temporal ha finalizado y las evalúa."""
        momento = ahora or ahora_utc()
        consulta = (
            select(PrediccionORM)
            .outerjoin(ResultadoPrediccionORM)
            .where(
                PrediccionORM.fecha_vencimiento_utc <= momento,
                ResultadoPrediccionORM.id.is_(None),
            )
        )
        pendientes = self.sesion.scalars(consulta).all()
        evaluados: list[ResultadoPrediccionORM] = []

        for p in pendientes:
            t_venc = a_utc(p.fecha_vencimiento_utc)
            res_precio = self.sincronizador.obtener_precio_cercano(t_venc)

            if res_precio is not None:
                precio_final, t_precio_final = res_precio
                p_inicial = p.precio_inicial_usd or precio_final

                if p_inicial > 0:
                    retorno_real = ((precio_final - p_inicial) / p_inicial) * 100.0
                else:
                    retorno_real = 0.0

                umbral = p.umbral_neutral_pct
                if retorno_real > umbral:
                    categoria_real = "ALCISTA"
                elif retorno_real < -umbral:
                    categoria_real = "BAJISTA"
                else:
                    categoria_real = "NEUTRAL"

                # Métricas del modelo (si fue probabilístico)
                acierto = None
                brier = None
                error_abs = None
                if (
                    p.probabilidad_alcista is not None
                    and p.probabilidad_bajista is not None
                    and p.probabilidad_neutral is not None
                ):
                    brier = calcular_brier_score(
                        p.probabilidad_alcista,
                        p.probabilidad_bajista,
                        p.probabilidad_neutral,
                        categoria_real,
                    )
                    probs = {
                        "ALCISTA": p.probabilidad_alcista,
                        "BAJISTA": p.probabilidad_bajista,
                        "NEUTRAL": p.probabilidad_neutral,
                    }
                    pred_cat = max(probs, key=probs.get)
                    acierto = pred_cat == categoria_real

                if p.retorno_esperado_pct is not None:
                    error_abs = abs(p.retorno_esperado_pct - retorno_real)

                # Baselines obligatorios (Principio VIII)
                # Persistencia: siempre predice neutral (retorno = 0)
                error_persistencia = abs(retorno_real)
                brier_persistencia = calcular_brier_score(0.0, 0.0, 1.0, categoria_real)

                resultado = ResultadoPrediccionORM(
                    prediccion_id=p.id,
                    estado_resultado="EVALUADO",
                    precio_final_usd=precio_final,
                    marca_tiempo_precio_final=t_precio_final,
                    retorno_real_pct=retorno_real,
                    resultado_categoria=categoria_real,
                    acierto_clasificacion=acierto,
                    brier_score=brier,
                    error_absoluto_modelo_pct=error_abs,
                    retorno_baseline_buy_hold_pct=retorno_real,
                    retorno_baseline_persistencia_pct=0.0,
                    brier_baseline_persistencia=brier_persistencia,
                    error_absoluto_persistencia_pct=error_persistencia,
                    notas="Evaluación completada con éxito.",
                )
                self.sesion.add(resultado)
                evaluados.append(resultado)

            else:
                # Comprobar si superó el periodo de gracia
                limite_gracia = t_venc + timedelta(days=self.config.dias_gracia_evaluacion)
                if ahora > limite_gracia:
                    resultado = ResultadoPrediccionORM(
                        prediccion_id=p.id,
                        estado_resultado="SIN_DATOS",
                        retorno_baseline_persistencia_pct=0.0,
                        notas="Precio final no disponible tras vencer periodo de gracia.",
                    )
                    self.sesion.add(resultado)
                    evaluados.append(resultado)

        self.sesion.flush()
        return evaluados
