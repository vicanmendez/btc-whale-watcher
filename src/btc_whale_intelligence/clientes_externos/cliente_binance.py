"""Cliente REST para Binance Public Market Data (RF-06).

Accede a precios spot, velas OHLCV y profundidad de mercado pública sin necesidad
de autenticación ni clave de API (Principio II).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .base import ClienteHttpBase

registro = logging.getLogger(__name__)


class ClienteBinance:
    def __init__(
        self,
        url_base: str = "https://data-api.binance.vision/api/v3",
        intervalo_min_seg: float = 0.2,
        cliente_http: Optional[ClienteHttpBase] = None,
    ) -> None:
        self._cliente = cliente_http or ClienteHttpBase(
            url_base,
            nombre="Binance Market",
            intervalo_minimo_seg=intervalo_min_seg,
        )

    def cerrar(self) -> None:
        self._cliente.cerrar()

    def obtener_precio_actual(self, par: str = "BTCUSDT") -> float:
        """Obtiene la última cotización spot negociada."""
        datos = self._cliente.obtener_json("/ticker/price", params={"symbol": par})
        return float(datos["price"])

    def obtener_resumen_24h(self, par: str = "BTCUSDT") -> dict[str, Any]:
        """Obtiene volumen, precio ponderado y cambio porcentual de las últimas 24h."""
        datos = self._cliente.obtener_json("/ticker/24hr", params={"symbol": par})
        return {
            "precio_ultimo": float(datos["lastPrice"]),
            "precio_ponderado": float(datos.get("weightedAvgPrice", datos["lastPrice"])),
            "variacion_24h_pct": float(datos["priceChangePercent"]),
            "volumen_btc": float(datos["volume"]),
            "volumen_usdt": float(datos["quoteVolume"]),
            "conteo_operaciones": int(datos["count"]),
        }

    def obtener_velas(
        self,
        par: str = "BTCUSDT",
        intervalo: str = "1h",
        limite: int = 500,
        inicio_ms: Optional[int] = None,
        fin_ms: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Descarga velas históricas (OHLCV) en formato normalizado."""
        params: dict[str, Any] = {"symbol": par, "interval": intervalo, "limit": limite}
        if inicio_ms is not None:
            params["startTime"] = inicio_ms
        if fin_ms is not None:
            params["endTime"] = fin_ms

        filas = self._cliente.obtener_json("/klines", params=params)
        velas: list[dict[str, Any]] = []
        for f in filas:
            t_apertura = datetime.fromtimestamp(f[0] / 1000.0, tz=timezone.utc)
            t_cierre = datetime.fromtimestamp(f[6] / 1000.0, tz=timezone.utc)
            velas.append(
                {
                    "par": par,
                    "intervalo": intervalo,
                    "marca_tiempo_apertura": t_apertura,
                    "marca_tiempo_cierre": t_cierre,
                    "precio_apertura": float(f[1]),
                    "precio_maximo": float(f[2]),
                    "precio_minimo": float(f[3]),
                    "precio_cierre": float(f[4]),
                    "volumen_btc": float(f[5]),
                    "volumen_usdt": float(f[7]),
                    "conteo_operaciones": int(f[8]),
                }
            )
        return velas

    def obtener_profundidad_mercado(
        self, par: str = "BTCUSDT", limite: int = 100
    ) -> dict[str, Any]:
        """Obtiene bids y asks del libro de órdenes para medir liquidez superficial (Capa A)."""
        datos = self._cliente.obtener_json("/depth", params={"symbol": par, "limit": limite})
        bids = [(float(p), float(q)) for p, q in datos.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in datos.get("asks", [])]
        return {"bids": bids, "asks": asks}
