"""Cliente HTTP base con timeouts, reintentos acotados, retroceso exponencial y cuotas (Principio XI)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable, Optional

import httpx

registro = logging.getLogger(__name__)

CODIGOS_REINTENTABLES = {408, 425, 429, 500, 502, 503, 504}


class ErrorProveedorExterno(RuntimeError):
    """Fallo definitivo (tras reintentos) al consultar una API externa."""

    def __init__(self, mensaje: str, codigo_http: Optional[int] = None, reintentable: bool = True) -> None:
        super().__init__(mensaje)
        self.codigo_http = codigo_http
        self.reintentable = reintentable


class ClienteHttpBase:
    """Cliente síncrono reutilizable.

    - `intervalo_minimo_seg`: separación mínima entre peticiones (respeto de cuotas).
    - `max_reintentos`: reintentos ante errores de red o códigos 408/425/429/5xx.
    - Respeta la cabecera `Retry-After` (acotada por `espera_maxima_seg`).
    - Los errores 4xx no reintentables (p. ej. 400, 404, 451) se propagan de inmediato.
    """

    def __init__(
        self,
        url_base: str,
        *,
        nombre: str,
        timeout_seg: float = 15.0,
        max_reintentos: int = 4,
        espera_base_seg: float = 1.0,
        espera_maxima_seg: float = 60.0,
        intervalo_minimo_seg: float = 0.0,
        transporte: Optional[httpx.BaseTransport] = None,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url_base = url_base.rstrip("/")
        self.nombre = nombre
        self.max_reintentos = max_reintentos
        self.espera_base_seg = espera_base_seg
        self.espera_maxima_seg = espera_maxima_seg
        self.intervalo_minimo_seg = intervalo_minimo_seg
        self._dormir = dormir
        self._reloj = reloj
        self._ultima_peticion: Optional[float] = None
        self._cliente = httpx.Client(
            timeout=httpx.Timeout(timeout_seg),
            transport=transporte,
            headers={"User-Agent": "btc-whale-intelligence/0.1 (+investigacion; sin fines comerciales)"},
            follow_redirects=True,
        )

    def cerrar(self) -> None:
        self._cliente.close()

    def _respetar_cuota(self) -> None:
        if self.intervalo_minimo_seg <= 0 or self._ultima_peticion is None:
            return
        transcurrido = self._reloj() - self._ultima_peticion
        if transcurrido < self.intervalo_minimo_seg:
            self._dormir(self.intervalo_minimo_seg - transcurrido)

    def _calcular_espera(self, intento: int, respuesta: Optional[httpx.Response]) -> float:
        if respuesta is not None:
            retry_after = respuesta.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), self.espera_maxima_seg)
                except ValueError:
                    pass
        espera = self.espera_base_seg * (2**intento)
        espera += random.uniform(0, self.espera_base_seg)  # jitter
        return min(espera, self.espera_maxima_seg)

    def _solicitar(self, ruta: str, params: Optional[dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.url_base}/{ruta.lstrip('/')}"
        ultimo_error: Optional[str] = None
        ultimo_codigo: Optional[int] = None
        for intento in range(self.max_reintentos + 1):
            self._respetar_cuota()
            respuesta: Optional[httpx.Response] = None
            try:
                self._ultima_peticion = self._reloj()
                respuesta = self._cliente.get(url, params=params)
            except httpx.TransportError as exc:
                ultimo_error = f"error de red: {type(exc).__name__}"
            else:
                if respuesta.status_code < 400:
                    return respuesta
                ultimo_codigo = respuesta.status_code
                ultimo_error = f"HTTP {respuesta.status_code}"
                if respuesta.status_code not in CODIGOS_REINTENTABLES:
                    raise ErrorProveedorExterno(
                        f"{self.nombre}: {ultimo_error} en {ruta}", respuesta.status_code, reintentable=False
                    )
            if intento < self.max_reintentos:
                espera = self._calcular_espera(intento, respuesta)
                registro.info("%s: %s en %s; reintento %d en %.1fs", self.nombre, ultimo_error, ruta, intento + 1, espera)
                self._dormir(espera)
        raise ErrorProveedorExterno(f"{self.nombre}: {ultimo_error} en {ruta} tras reintentos", ultimo_codigo)

    def obtener_json(self, ruta: str, params: Optional[dict[str, Any]] = None) -> Any:
        respuesta = self._solicitar(ruta, params)
        try:
            return respuesta.json()
        except ValueError as exc:
            raise ErrorProveedorExterno(f"{self.nombre}: respuesta JSON inválida en {ruta}") from exc

    def obtener_texto(self, ruta: str, params: Optional[dict[str, Any]] = None) -> str:
        return self._solicitar(ruta, params).text.strip()
