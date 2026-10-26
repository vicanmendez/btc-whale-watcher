"""Ingeniería de características contextuales con información anterior al evento (RF-06, RF-09, Principio VII).

Garantiza la ausencia de lookahead bias: todas las métricas se computan exclusivamente
sobre observaciones con marca temporal <= evento.marca_tiempo_referencia.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..base_datos.modelos import CaracteristicaCalculadaORM, EventoAnalizadoORM, TransaccionOnChainORM
from ..mercado.sincronizador_mercado import SincronizadorMercado
from ..tiempo import ahora_utc

registro = logging.getLogger(__name__)


class ExtractorCaracteristicas:
    def __init__(self, sesion: Session, sincronizador_mercado: SincronizadorMercado) -> None:
        self.sesion = sesion
        self.sincronizador = sincronizador_mercado

    def calcular_flujo_neto_entidad_24h(
        self, entidad_id: int, momento_referencia
    ) -> Optional[float]:
        """Calcula las entradas netas menos salidas atribuibles a la entidad en las 24h previas."""
        inicio_24h = momento_referencia - timedelta(hours=24)
        consulta_entradas = (
            select(func.sum(EventoAnalizadoORM.monto_relevante_btc))
            .where(
                EventoAnalizadoORM.entidad_destino_id == entidad_id,
                EventoAnalizadoORM.marca_tiempo_referencia >= inicio_24h,
                EventoAnalizadoORM.marca_tiempo_referencia <= momento_referencia,
            )
        )
        consulta_salidas = (
            select(func.sum(EventoAnalizadoORM.monto_relevante_btc))
            .where(
                EventoAnalizadoORM.entidad_origen_id == entidad_id,
                EventoAnalizadoORM.marca_tiempo_referencia >= inicio_24h,
                EventoAnalizadoORM.marca_tiempo_referencia <= momento_referencia,
            )
        )
        entradas = self.sesion.scalar(consulta_entradas) or 0.0
        salidas = self.sesion.scalar(consulta_salidas) or 0.0
        return float(entradas - salidas)

    def extraer_y_persistir(
        self,
        evento: EventoAnalizadoORM,
        profundidad_mercado: Optional[dict] = None,
    ) -> CaracteristicaCalculadaORM:
        """Calcula y almacena en base de datos el vector de características del evento."""
        existente = (
            self.sesion.query(CaracteristicaCalculadaORM)
            .filter(CaracteristicaCalculadaORM.evento_id == evento.id)
            .first()
        )
        if existente is not None:
            return existente

        faltantes: list[str] = []
        t_ref = evento.marca_tiempo_referencia

        # 1. Precio spot de referencia
        res_precio = self.sincronizador.obtener_precio_cercano(t_ref)
        if res_precio is not None:
            precio_ref, t_precio = res_precio
            evento.precio_referencia_usd = precio_ref
        else:
            precio_ref, t_precio = None, None
            faltantes.append("precio_referencia_usd")

        # 2. Retornos 1h y 24h previos
        retorno_1h = self.sincronizador.calcular_retorno_historico_pct(t_ref, horas_hacia_atras=1)
        if retorno_1h is None:
            faltantes.append("variacion_precio_1h_pct")

        retorno_24h = self.sincronizador.calcular_retorno_historico_pct(t_ref, horas_hacia_atras=24)
        if retorno_24h is None:
            faltantes.append("variacion_precio_24h_pct")

        # 3. Volatilidad histórica 7d previa
        vol_7d = self.sincronizador.calcular_volatilidad_7d(t_ref)
        if vol_7d is None:
            faltantes.append("volatilidad_historica_7d")

        # 4. Volumen 24h aproximado y ratio
        volumen_24h = None
        ratio_vol = None
        try:
            resumen_24h = self.sincronizador.cliente.obtener_resumen_24h()
            volumen_24h = float(resumen_24h["volumen_btc"])
            if volumen_24h > 0:
                ratio_vol = float(evento.monto_relevante_btc / volumen_24h)
        except Exception:
            faltantes.append("volumen_24h_btc")

        # 5. Flujo neto de la entidad
        flujo_entidad = None
        ent_interes = evento.entidad_destino_id or evento.entidad_origen_id
        if ent_interes is not None:
            flujo_entidad = self.calcular_flujo_neto_entidad_24h(ent_interes, t_ref)

        # 6. Conteo de eventos previos 24h
        inicio_24h = t_ref - timedelta(hours=24)
        conteo_previos = (
            self.sesion.scalar(
                select(func.count(EventoAnalizadoORM.id)).where(
                    EventoAnalizadoORM.marca_tiempo_referencia >= inicio_24h,
                    EventoAnalizadoORM.marca_tiempo_referencia < t_ref,
                )
            )
            or 0
        )

        # 7. Profundidad superficial de mercado
        prof_compra = None
        prof_venta = None
        if profundidad_mercado and precio_ref:
            # Sumar volumen dentro de +-2% del precio
            bids = profundidad_mercado.get("bids", [])
            asks = profundidad_mercado.get("asks", [])
            umbral_bid = precio_ref * 0.98
            umbral_ask = precio_ref * 1.02
            prof_compra = sum(p * q for p, q in bids if p >= umbral_bid)
            prof_venta = sum(p * q for p, q in asks if p <= umbral_ask)
        else:
            faltantes.append("profundidad_mercado_2pct")

        caracteristica = CaracteristicaCalculadaORM(
            evento_id=evento.id,
            precio_referencia_usd=precio_ref,
            marca_tiempo_precio=t_precio,
            volumen_24h_btc=volumen_24h,
            ratio_monto_volumen_24h=ratio_vol,
            variacion_precio_1h_pct=retorno_1h,
            variacion_precio_24h_pct=retorno_24h,
            volatilidad_historica_7d=vol_7d,
            flujo_neto_entidad_24h_btc=flujo_entidad,
            conteo_eventos_previos_24h=int(conteo_previos),
            profundidad_compra_2pct_usd=prof_compra,
            profundidad_venta_2pct_usd=prof_venta,
            datos_faltantes=json.dumps(faltantes) if faltantes else None,
            calculado_en=ahora_utc(),
        )
        self.sesion.add(caracteristica)
        evento.estado_procesamiento = "ENRIQUECIDO"
        self.sesion.flush()
        return caracteristica
