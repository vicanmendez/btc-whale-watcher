"""Sincronizador y repositorio de velas y contexto de mercado (RF-06)."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..base_datos.modelos import VelaMercadoORM
from ..clientes_externos.cliente_binance import ClienteBinance
from ..configuracion import Configuracion
from ..tiempo import a_epoch_ms, a_utc

registro = logging.getLogger(__name__)


class SincronizadorMercado:
    def __init__(
        self, sesion: Session, config: Configuracion, cliente_binance: Optional[ClienteBinance] = None
    ) -> None:
        self.sesion = sesion
        self.config = config
        self.cliente = cliente_binance or ClienteBinance(
            url_base=config.url_binance,
            intervalo_min_seg=config.mercado_intervalo_min_seg,
        )

    def persistir_velas(self, velas: list[dict]) -> int:
        """Inserta o actualiza velas en velas_mercado de forma idempotente."""
        insertadas = 0
        for v in velas:
            consulta = select(VelaMercadoORM).where(
                VelaMercadoORM.fuente == "Binance",
                VelaMercadoORM.par == v["par"],
                VelaMercadoORM.intervalo == v["intervalo"],
                VelaMercadoORM.marca_tiempo_apertura == v["marca_tiempo_apertura"],
            )
            existente = self.sesion.scalars(consulta).first()
            if existente is None:
                vela = VelaMercadoORM(
                    fuente="Binance",
                    par=v["par"],
                    intervalo=v["intervalo"],
                    marca_tiempo_apertura=v["marca_tiempo_apertura"],
                    marca_tiempo_cierre=v["marca_tiempo_cierre"],
                    precio_apertura=v["precio_apertura"],
                    precio_maximo=v["precio_maximo"],
                    precio_minimo=v["precio_minimo"],
                    precio_cierre=v["precio_cierre"],
                    volumen_btc=v["volumen_btc"],
                    volumen_usdt=v["volumen_usdt"],
                    conteo_operaciones=v["conteo_operaciones"],
                )
                self.sesion.add(vela)
                insertadas += 1
            else:
                existente.precio_cierre = v["precio_cierre"]
                existente.volumen_btc = v["volumen_btc"]
                existente.volumen_usdt = v["volumen_usdt"]

        self.sesion.flush()
        return insertadas

    def sincronizar_velas_recientes(
        self, par: str = "BTCUSDT", intervalos: Sequence[str] = ("1m", "1h", "1d")
    ) -> dict[str, int]:
        """Descarga las últimas velas para cada intervalo configurado."""
        resultado: dict[str, int] = {}
        for intervalo in intervalos:
            try:
                velas = self.cliente.obtener_velas(par=par, intervalo=intervalo, limite=100)
                n = self.persistir_velas(velas)
                resultado[intervalo] = n
                registro.info("Velas sincronizadas (%s %s): %d nuevas", par, intervalo, n)
            except Exception as exc:
                registro.warning("Error sincronizando velas (%s %s): %s", par, intervalo, exc)
                resultado[intervalo] = 0
        return resultado

    def obtener_precio_cercano(
        self, momento: datetime, par: str = "BTCUSDT"
    ) -> Optional[tuple[float, datetime]]:
        """Busca el precio de cierre más cercano al momento dado dentro de la tolerancia configurada.

        Retorna (precio_usd, marca_tiempo_encontrada) o None.
        """
        momento_utc = a_utc(momento)
        tolerancia = timedelta(minutes=self.config.tolerancia_precio_min)
        inicio = momento_utc - tolerancia
        fin = momento_utc + tolerancia

        consulta = (
            select(VelaMercadoORM)
            .where(
                VelaMercadoORM.par == par,
                VelaMercadoORM.intervalo.in_(["1m", "1h"]),
                VelaMercadoORM.marca_tiempo_apertura >= inicio,
                VelaMercadoORM.marca_tiempo_apertura <= fin,
            )
            .order_by(VelaMercadoORM.intervalo.asc())  # Prefiere 1m sobre 1h
        )
        velas = self.sesion.scalars(consulta).all()
        if not velas:
            # Intento de descarga bajo demanda si la API está accesible
            try:
                inicio_ms = a_epoch_ms(inicio)
                fin_ms = a_epoch_ms(fin)
                velas_remotas = self.cliente.obtener_velas(
                    par=par, intervalo="1m", limite=10, inicio_ms=inicio_ms, fin_ms=fin_ms
                )
                if velas_remotas:
                    self.persistir_velas(velas_remotas)
                    return float(velas_remotas[-1]["precio_cierre"]), velas_remotas[-1]["marca_tiempo_apertura"]
            except Exception:
                pass
            return None

        # Escoger la vela con menor delta de tiempo
        mejor_vela = min(velas, key=lambda v: abs(v.marca_tiempo_apertura - momento_utc))
        return float(mejor_vela.precio_cierre), mejor_vela.marca_tiempo_apertura

    def calcular_retorno_historico_pct(
        self, momento_referencia: datetime, horas_hacia_atras: int, par: str = "BTCUSDT"
    ) -> Optional[float]:
        """Calcula el cambio porcentual del precio entre (momento - horas) y momento."""
        res_actual = self.obtener_precio_cercano(momento_referencia, par)
        if res_actual is None:
            return None
        precio_actual, _ = res_actual

        momento_previo = a_utc(momento_referencia) - timedelta(hours=horas_hacia_atras)
        res_previo = self.obtener_precio_cercano(momento_previo, par)
        if res_previo is None:
            return None
        precio_previo, _ = res_previo

        if precio_previo <= 0:
            return None
        return ((precio_actual - precio_previo) / precio_previo) * 100.0

    def calcular_volatilidad_7d(
        self, momento_referencia: datetime, par: str = "BTCUSDT"
    ) -> Optional[float]:
        """Calcula la desviación estándar anualizada de retornos logarítmicos horarios en 7 días previos."""
        momento_utc = a_utc(momento_referencia)
        hace_7d = momento_utc - timedelta(days=7)

        consulta = (
            select(VelaMercadoORM.precio_cierre)
            .where(
                VelaMercadoORM.par == par,
                VelaMercadoORM.intervalo == "1h",
                VelaMercadoORM.marca_tiempo_apertura >= hace_7d,
                VelaMercadoORM.marca_tiempo_apertura <= momento_utc,
            )
            .order_by(VelaMercadoORM.marca_tiempo_apertura.asc())
        )
        precios = self.sesion.scalars(consulta).all()
        if len(precios) < 24:  # Al menos 24 horas de datos
            return None

        arr = np.array(precios, dtype=float)
        retornos = np.diff(np.log(arr))
        desv_std = float(np.std(retornos))
        # Anualización horaria: sqrt(24 * 365)
        factor_anual = math.sqrt(24 * 365)
        return desv_std * factor_anual
