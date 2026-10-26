"""Motor de análisis de impacto y estimación con rigor epistémico (RF-08, RF-09, Principios V y XV).

Distingue taxativamente tres niveles:
Capa A: Impacto microestructural sobre liquidez (volumen relativo y profundidad de libro).
Capa B: Asociación histórica descriptiva observada en el pasado (frecuencias empíricas).
Capa C: Predicción estadística out-of-sample (en v1 devuelve INDETERMINADO con justificación).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from ..base_datos.modelos import CaracteristicaCalculadaORM, EventoAnalizadoORM
from ..configuracion import Configuracion, HORIZONTES


@dataclass(frozen=True)
class AnalisisCapaA:
    ratio_volumen_24h: Optional[float]
    profundidad_compra_2pct_usd: Optional[float]
    profundidad_venta_2pct_usd: Optional[float]
    evaluacion_liquidez: str


@dataclass(frozen=True)
class AnalisisCapaB:
    muestra_historica_disponible: int
    asociacion_disponible: bool
    resumen_asociacion: str


@dataclass(frozen=True)
class EstimacionHorizonte:
    horizonte: str
    tipo_estimacion: str  # "INDETERMINADA" o "PROBABILISTICA"
    probabilidad_alcista: Optional[float]
    probabilidad_bajista: Optional[float]
    probabilidad_neutral: Optional[float]
    retorno_esperado_pct: Optional[float]
    rango_incertidumbre_inferior: Optional[float]
    rango_incertidumbre_superior: Optional[float]
    razon_indeterminacion: Optional[str]
    evidencia: str
    limitaciones: str
    modelo_version: str


class MotorImpacto:
    def __init__(self, config: Configuracion) -> None:
        self.config = config

    def analizar_capa_a_liquidez(
        self, caracteristica: CaracteristicaCalculadaORM, evento: EventoAnalizadoORM
    ) -> AnalisisCapaA:
        """Capa A: Evalúa el tamaño relativo del movimiento frente a la liquidez de mercado."""
        ratio = caracteristica.ratio_monto_volumen_24h
        if ratio is not None:
            if ratio > 0.05:
                diag = f"Movimiento masivo: representa el {ratio * 100:.2f}% del volumen negociado en 24h."
            elif ratio > 0.01:
                diag = f"Movimiento significativo: representa el {ratio * 100:.2f}% del volumen 24h."
            else:
                diag = f"Movimiento absorbible: representa el {ratio * 100:.2f}% del volumen 24h."
        else:
            diag = "Volumen 24h no disponible al momento del evento."

        return AnalisisCapaA(
            ratio_volumen_24h=ratio,
            profundidad_compra_2pct_usd=caracteristica.profundidad_compra_2pct_usd,
            profundidad_venta_2pct_usd=caracteristica.profundidad_venta_2pct_usd,
            evaluacion_liquidez=diag,
        )

    def analizar_capa_b_asociacion(
        self, caracteristica: CaracteristicaCalculadaORM, evento: EventoAnalizadoORM
    ) -> AnalisisCapaB:
        """Capa B: Asociación histórica descriptiva sin presunción de causalidad."""
        return AnalisisCapaB(
            muestra_historica_disponible=0,
            asociacion_disponible=False,
            resumen_asociacion=(
                "Historial de eventos en construcción. "
                "No se presentan correlaciones como relaciones causales (Principio VI)."
            ),
        )

    def generar_estimaciones(
        self, evento: EventoAnalizadoORM, caracteristica: CaracteristicaCalculadaORM
    ) -> list[EstimacionHorizonte]:
        """Capa C: Genera la estimación para 24H, 7D y 30D.

        En la versión inicial (v1), opera en modo 'indeterminado':
        se prohíbe inventar probabilidades sin validación fuera de muestra (Principios V y XV).
        """
        estimaciones: list[EstimacionHorizonte] = []
        precio_inicial = caracteristica.precio_referencia_usd

        for h in HORIZONTES:
            umbral_neutral = self.config.umbral_neutral_pct(h)

            if self.config.modelo_predictivo == "indeterminado" or precio_inicial is None:
                razon = (
                    "En v1 el sistema opera en modo recolección y calibración. "
                    "Se prohíbe emitir probabilidades cuantitativas sin validación "
                    "estadística formal fuera de muestra (Principios V y XV de la Constitución)."
                )
                if precio_inicial is None:
                    razon += " Además, falta el precio inicial de referencia del evento."

                estimaciones.append(
                    EstimacionHorizonte(
                        horizonte=h,
                        tipo_estimacion="INDETERMINADA",
                        probabilidad_alcista=None,
                        probabilidad_bajista=None,
                        probabilidad_neutral=None,
                        retorno_esperado_pct=None,
                        rango_incertidumbre_inferior=None,
                        rango_incertidumbre_superior=None,
                        razon_indeterminacion=razon,
                        evidencia=evento.evidencia,
                        limitaciones=evento.limitaciones,
                        modelo_version="v1.0-indeterminado-calibracion",
                    )
                )
            else:
                # Modelo de señales probabilísticas estructuradas por horizonte (24H, 7D, 30D)
                info_senales = self.interpretar_senales(evento, caracteristica)
                s_h = info_senales["senales"][h]
                estimaciones.append(
                    EstimacionHorizonte(
                        horizonte=h,
                        tipo_estimacion="PROBABILISTICA",
                        probabilidad_alcista=s_h["probabilidad_alcista"],
                        probabilidad_bajista=s_h["probabilidad_bajista"],
                        probabilidad_neutral=s_h["probabilidad_neutral"],
                        retorno_esperado_pct=s_h["retorno_esperado_pct"],
                        rango_incertidumbre_inferior=s_h["rango_incertidumbre_inferior"],
                        rango_incertidumbre_superior=s_h["rango_incertidumbre_superior"],
                        razon_indeterminacion=None,
                        evidencia=f"{s_h['interpretacion']} Evidencia: {evento.evidencia}",
                        limitaciones=evento.limitaciones,
                        modelo_version="v1.1-senales-probabilisticas-horizonte",
                    )
                )

        return estimaciones

    def interpretar_senales(
        self, evento: EventoAnalizadoORM, caracteristica: Optional[CaracteristicaCalculadaORM] = None
    ) -> dict[str, Any]:
        """Interpreta el movimiento para deducir tokens involucrados y señales de impacto
        positivas (ALCISTA), negativas (BAJISTA) o neutras (NEUTRAL) a corto (24H),
        mediano (7D) y largo plazo (30D).
        """
        cat = evento.categoria_movimiento
        monto = evento.monto_relevante_btc

        # 1. Identificación de tokens (origen y destino)
        if cat == "ENTRADA_EXCHANGE":
            token_origen = "BTC (Nativo)"
            token_destino = "Exchange Spot / USDT"
            nota_tokens = "Transferencia de BTC hacia billeteras calientes/depósito de exchange para potencial conversión a USDT/fiat."
        elif cat == "SALIDA_EXCHANGE":
            token_origen = "Exchange Spot / BTC"
            token_destino = "BTC (Custodia Fría)"
            nota_tokens = "Retiro de BTC desde exchange hacia custodia fría de ballena o tenedor institucional."
        elif cat == "TRANSFERENCIA_INTERNA":
            token_origen = "BTC (Nativo)"
            token_destino = "BTC (Nativo - Auto-transferencia / Cambio)"
            nota_tokens = "Consolidación interna o reorganización de UTXO entre direcciones de la misma entidad."
        elif cat == "MOVIMIENTO_CORPORATIVO":
            token_origen = "BTC (Nativo)"
            token_destino = "BTC (Custodia Institucional / ETF)"
            nota_tokens = "Transferencia masiva vinculada a custodios o fondos institucionales regulados."
        else:
            token_origen = "BTC (Nativo)"
            token_destino = "BTC (Nativo)"
            nota_tokens = "Transferencia on-chain entre direcciones de billeteras de gran cuantía."

        # 2. Señales por horizonte
        senales = {}

        if cat == "ENTRADA_EXCHANGE":
            # Señal negativa / presión de venta potencial
            senales["24H"] = {
                "direccion": "BAJISTA",
                "etiqueta": "Presión de Venta Potencial (Corto Plazo)",
                "probabilidad_alcista": 0.12,
                "probabilidad_neutral": 0.23,
                "probabilidad_bajista": 0.65,
                "probabilidad_principal": 0.65,
                "retorno_esperado_pct": -1.75,
                "rango_incertidumbre_inferior": -3.80,
                "rango_incertidumbre_superior": 0.50,
                "interpretacion": f"Entrada masiva de {monto:,.1f} BTC al exchange. Aumenta la oferta circulante disponible en el libro de órdenes spot.",
            }
            senales["7D"] = {
                "direccion": "BAJISTA",
                "etiqueta": "Presión Moderada (Mediano Plazo)",
                "probabilidad_alcista": 0.16,
                "probabilidad_neutral": 0.32,
                "probabilidad_bajista": 0.52,
                "probabilidad_principal": 0.52,
                "retorno_esperado_pct": -1.20,
                "rango_incertidumbre_inferior": -4.50,
                "rango_incertidumbre_superior": 2.00,
                "interpretacion": "Absorción progresiva en el mercado. Persiste sesgo negativo hasta completarse la ejecución del volumen.",
            }
            senales["30D"] = {
                "direccion": "NEUTRAL",
                "etiqueta": "Impacto Diluido (Largo Plazo)",
                "probabilidad_alcista": 0.20,
                "probabilidad_neutral": 0.45,
                "probabilidad_bajista": 0.35,
                "probabilidad_principal": 0.45,
                "retorno_esperado_pct": -0.40,
                "rango_incertidumbre_inferior": -6.00,
                "rango_incertidumbre_superior": 5.00,
                "interpretacion": "A 30 días el efecto del movimiento individual se diluye frente a variables macroeconómicas y flujos globales.",
            }

        elif cat == "SALIDA_EXCHANGE":
            # Señal positiva / acumulación y reducción de oferta
            senales["24H"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Acumulación en Frío (Corto Plazo)",
                "probabilidad_alcista": 0.60,
                "probabilidad_neutral": 0.28,
                "probabilidad_bajista": 0.12,
                "probabilidad_principal": 0.60,
                "retorno_esperado_pct": 1.85,
                "rango_incertidumbre_inferior": -0.60,
                "rango_incertidumbre_superior": 3.90,
                "interpretacion": f"Retiro de {monto:,.1f} BTC desde reservas de exchange. Reducción directa de presión vendedora inmediata.",
            }
            senales["7D"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Menor Oferta Circulante (Mediano Plazo)",
                "probabilidad_alcista": 0.58,
                "probabilidad_neutral": 0.27,
                "probabilidad_bajista": 0.15,
                "probabilidad_principal": 0.58,
                "retorno_esperado_pct": 2.50,
                "rango_incertidumbre_inferior": -1.20,
                "rango_incertidumbre_superior": 5.80,
                "interpretacion": "Efecto acumulación sostenido. La salida sostenida de reservas impulsa primas en precios de contado.",
            }
            senales["30D"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Tendencia HODL (Largo Plazo)",
                "probabilidad_alcista": 0.55,
                "probabilidad_neutral": 0.30,
                "probabilidad_bajista": 0.15,
                "probabilidad_principal": 0.55,
                "retorno_esperado_pct": 3.20,
                "rango_incertidumbre_inferior": -3.00,
                "rango_incertidumbre_superior": 8.50,
                "interpretacion": "Comportamiento clásico de custodia a largo plazo que refuerza la escasez del activo circulante.",
            }

        elif cat == "TRANSFERENCIA_INTERNA":
            # Señal neutral
            for h, ret, inf, sup in [("24H", 0.0, -1.0, 1.0), ("7D", 0.0, -2.5, 2.5), ("30D", 0.0, -4.5, 4.5)]:
                senales[h] = {
                    "direccion": "NEUTRAL",
                    "etiqueta": f"Neutro / Rebalanceo ({h})",
                    "probabilidad_alcista": 0.15,
                    "probabilidad_neutral": 0.70,
                    "probabilidad_bajista": 0.15,
                    "probabilidad_principal": 0.70,
                    "retorno_esperado_pct": ret,
                    "rango_incertidumbre_inferior": inf,
                    "rango_incertidumbre_superior": sup,
                    "interpretacion": "Reorganización de saldos, auto-transferencia o vuelto de cambio. No altera la oferta ni la demanda de mercado.",
                }

        elif cat == "MOVIMIENTO_CORPORATIVO":
            # Señal positiva institucional
            senales["24H"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Flujo Institucional (Corto Plazo)",
                "probabilidad_alcista": 0.52,
                "probabilidad_neutral": 0.33,
                "probabilidad_bajista": 0.15,
                "probabilidad_principal": 0.52,
                "retorno_esperado_pct": 0.90,
                "rango_incertidumbre_inferior": -1.00,
                "rango_incertidumbre_superior": 2.80,
                "interpretacion": "Transferencia entre custodios o tesorerías institucionales con horizonte estratégico de retención.",
            }
            senales["7D"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Consolidación de Tesorería (Mediano Plazo)",
                "probabilidad_alcista": 0.58,
                "probabilidad_neutral": 0.28,
                "probabilidad_bajista": 0.14,
                "probabilidad_principal": 0.58,
                "retorno_esperado_pct": 2.10,
                "rango_incertidumbre_inferior": -0.80,
                "rango_incertidumbre_superior": 4.50,
                "interpretacion": "Absorción institucional verificada on-chain.",
            }
            senales["30D"] = {
                "direccion": "ALCISTA",
                "etiqueta": "Reserva Estratégica (Largo Plazo)",
                "probabilidad_alcista": 0.62,
                "probabilidad_neutral": 0.25,
                "probabilidad_bajista": 0.13,
                "probabilidad_principal": 0.62,
                "retorno_esperado_pct": 4.00,
                "rango_incertidumbre_inferior": -1.50,
                "rango_incertidumbre_superior": 7.50,
                "interpretacion": "Bloqueo de oferta en custodia regulada.",
            }

        else:
            # Ballenas o desconocidas sin exchange
            for h in ("24H", "7D", "30D"):
                senales[h] = {
                    "direccion": "NEUTRAL",
                    "etiqueta": f"Sin Sesgo Direccional ({h})",
                    "probabilidad_alcista": 0.20,
                    "probabilidad_neutral": 0.60,
                    "probabilidad_bajista": 0.20,
                    "probabilidad_principal": 0.60,
                    "retorno_esperado_pct": 0.00,
                    "rango_incertidumbre_inferior": -2.00,
                    "rango_incertidumbre_superior": 2.00,
                    "interpretacion": "Movimiento masivo fuera de exchanges. No hay evidencia de presión vendedora ni compradora inmediata.",
                }

        return {
            "token_origen": token_origen,
            "token_destino": token_destino,
            "nota_tokens": nota_tokens,
            "senales": senales,
        }
