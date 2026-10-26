"""Carga y validación de la configuración desde variables de entorno (Principio XII y RF-14).

Ningún parámetro operativo está fijado en el código: todo se lee del entorno o de
un archivo `.env`. Las credenciales nunca aparecen en `repr()` ni en los logs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Mapping, Optional

HORIZONTES: tuple[str, ...] = ("24H", "7D", "30D")


class ErrorConfiguracion(ValueError):
    """La configuración es inválida o incompleta."""


def _a_bool(valor: str, nombre: str) -> bool:
    normalizado = valor.strip().lower()
    if normalizado in {"1", "true", "si", "sí", "yes", "on"}:
        return True
    if normalizado in {"0", "false", "no", "off", ""}:
        return False
    raise ErrorConfiguracion(f"{nombre}: valor booleano inválido")


def _a_float(valor: str, nombre: str) -> float:
    try:
        return float(valor)
    except ValueError as exc:
        raise ErrorConfiguracion(f"{nombre}: se esperaba un número") from exc


def _a_int(valor: str, nombre: str) -> int:
    try:
        return int(valor)
    except ValueError as exc:
        raise ErrorConfiguracion(f"{nombre}: se esperaba un entero") from exc


@dataclass(frozen=True)
class Configuracion:
    # Persistencia y logs
    url_base_datos: str = "sqlite:///datos/ballenas.db"
    nivel_log: str = "INFO"
    archivo_log: Optional[str] = "logs/whalewatcher.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_respaldos: int = 5

    # On-chain
    url_mempool: str = "https://mempool.space/api"
    url_esplora_respaldo: Optional[str] = "https://blockstream.info/api"
    onchain_intervalo_min_seg: float = 0.5
    escanear_bloques_completos: bool = True
    max_bloques_por_ciclo: int = 3
    max_direcciones_por_ciclo: int = 25
    vigilar_mempool_direcciones: bool = True

    # Mercado
    url_binance: str = "https://data-api.binance.vision/api/v3"
    par_mercado: str = "BTCUSDT"
    mercado_intervalo_min_seg: float = 0.2
    tolerancia_precio_min: int = 5

    # Umbrales
    umbral_exchange_btc: float = 500.0
    umbral_institucional_btc: float = 250.0
    umbral_desconocido_btc: float = 1000.0
    certeza_minima_atribucion: float = 0.7

    # Análisis
    umbral_neutral_24h_pct: float = 1.0
    umbral_neutral_7d_pct: float = 3.0
    umbral_neutral_30d_pct: float = 6.0
    modelo_predictivo: str = "indeterminado"
    muestra_minima_asociacion: int = 30
    fraccion_reserva_final: float = 0.2
    muestra_minima_validacion: int = 100
    dias_gracia_evaluacion: int = 3

    # SMTP
    alertas_habilitadas: bool = True
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_contrasena: str = field(default="", repr=False)
    smtp_remitente: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seg: float = 20.0
    destinatarios_alerta: tuple[str, ...] = ()
    max_intentos_alerta: int = 5
    url_explorador_tx: str = "https://mempool.space/tx/"

    def __post_init__(self) -> None:
        if not 0.0 <= self.certeza_minima_atribucion <= 1.0:
            raise ErrorConfiguracion("CERTEZA_MINIMA_ATRIBUCION debe estar entre 0 y 1")
        for nombre in ("umbral_exchange_btc", "umbral_institucional_btc", "umbral_desconocido_btc"):
            if getattr(self, nombre) < 0:
                raise ErrorConfiguracion(f"{nombre.upper()} no puede ser negativo")
        for nombre in ("umbral_neutral_24h_pct", "umbral_neutral_7d_pct", "umbral_neutral_30d_pct"):
            if getattr(self, nombre) <= 0:
                raise ErrorConfiguracion(f"{nombre.upper()} debe ser positivo")
        if not 0.0 < self.fraccion_reserva_final < 1.0:
            raise ErrorConfiguracion("FRACCION_RESERVA_FINAL debe estar entre 0 y 1 (exclusivo)")
        if self.smtp_ssl and self.smtp_starttls:
            raise ErrorConfiguracion("SMTP_SSL y SMTP_STARTTLS son excluyentes")
        if self.max_bloques_por_ciclo < 1 or self.max_direcciones_por_ciclo < 0:
            raise ErrorConfiguracion("Límites por ciclo inválidos")

    def umbral_neutral_pct(self, horizonte: str) -> float:
        return {
            "24H": self.umbral_neutral_24h_pct,
            "7D": self.umbral_neutral_7d_pct,
            "30D": self.umbral_neutral_30d_pct,
        }[horizonte]

    def secretos(self) -> tuple[str, ...]:
        """Valores que nunca deben aparecer en los logs."""
        return tuple(s for s in (self.smtp_contrasena,) if s)

    def smtp_configurado(self) -> bool:
        return bool(self.smtp_host and self.smtp_remitente and self.destinatarios_alerta)


# Mapa variable de entorno -> (atributo, conversor)
_MAPA_ENTORNO: dict[str, tuple[str, str]] = {
    "DATABASE_URL": ("url_base_datos", "str"),
    "LOG_LEVEL": ("nivel_log", "str"),
    "LOG_FILE": ("archivo_log", "str_opcional"),
    "LOG_MAX_BYTES": ("log_max_bytes", "int"),
    "LOG_BACKUPS": ("log_respaldos", "int"),
    "MEMPOOL_API_URL": ("url_mempool", "str"),
    "ESPLORA_FALLBACK_URL": ("url_esplora_respaldo", "str_opcional"),
    "ONCHAIN_INTERVALO_MIN_SEG": ("onchain_intervalo_min_seg", "float"),
    "ESCANEAR_BLOQUES_COMPLETOS": ("escanear_bloques_completos", "bool"),
    "MAX_BLOQUES_POR_CICLO": ("max_bloques_por_ciclo", "int"),
    "MAX_DIRECCIONES_POR_CICLO": ("max_direcciones_por_ciclo", "int"),
    "VIGILAR_MEMPOOL_DIRECCIONES": ("vigilar_mempool_direcciones", "bool"),
    "BINANCE_API_URL": ("url_binance", "str"),
    "PAR_MERCADO": ("par_mercado", "str"),
    "MERCADO_INTERVALO_MIN_SEG": ("mercado_intervalo_min_seg", "float"),
    "TOLERANCIA_PRECIO_MIN": ("tolerancia_precio_min", "int"),
    "UMBRAL_EXCHANGE_BTC": ("umbral_exchange_btc", "float"),
    "UMBRAL_INSTITUCIONAL_BTC": ("umbral_institucional_btc", "float"),
    "UMBRAL_DESCONOCIDO_BTC": ("umbral_desconocido_btc", "float"),
    "CERTEZA_MINIMA_ATRIBUCION": ("certeza_minima_atribucion", "float"),
    "UMBRAL_NEUTRAL_24H_PCT": ("umbral_neutral_24h_pct", "float"),
    "UMBRAL_NEUTRAL_7D_PCT": ("umbral_neutral_7d_pct", "float"),
    "UMBRAL_NEUTRAL_30D_PCT": ("umbral_neutral_30d_pct", "float"),
    "MODELO_PREDICTIVO": ("modelo_predictivo", "str"),
    "MUESTRA_MINIMA_ASOCIACION": ("muestra_minima_asociacion", "int"),
    "FRACCION_RESERVA_FINAL": ("fraccion_reserva_final", "float"),
    "MUESTRA_MINIMA_VALIDACION": ("muestra_minima_validacion", "int"),
    "DIAS_GRACIA_EVALUACION": ("dias_gracia_evaluacion", "int"),
    "ALERTAS_HABILITADAS": ("alertas_habilitadas", "bool"),
    "SMTP_HOST": ("smtp_host", "str"),
    "SMTP_PORT": ("smtp_puerto", "int"),
    "SMTP_USER": ("smtp_usuario", "str"),
    "SMTP_PASSWORD": ("smtp_contrasena", "str"),
    "SMTP_FROM": ("smtp_remitente", "str"),
    "SMTP_STARTTLS": ("smtp_starttls", "bool"),
    "SMTP_SSL": ("smtp_ssl", "bool"),
    "SMTP_TIMEOUT_SEG": ("smtp_timeout_seg", "float"),
    "ALERT_EMAIL_TO": ("destinatarios_alerta", "lista"),
    "MAX_INTENTOS_ALERTA": ("max_intentos_alerta", "int"),
    "EXPLORADOR_TX_URL": ("url_explorador_tx", "str"),
}


def cargar_configuracion(
    entorno: Optional[Mapping[str, str]] = None,
    archivo_env: Optional[str | Path] = ".env",
) -> Configuracion:
    """Construye la configuración a partir de `entorno` (por defecto `os.environ`).

    Si `entorno` es None se intenta cargar `archivo_env` con python-dotenv sin
    sobrescribir variables ya definidas en el proceso.
    """
    if entorno is None:
        if archivo_env and Path(archivo_env).exists():
            from dotenv import load_dotenv

            load_dotenv(archivo_env, override=False)
        entorno = os.environ

    valores: dict[str, object] = {}
    for variable, (atributo, tipo) in _MAPA_ENTORNO.items():
        if variable not in entorno:
            continue
        crudo = entorno[variable]
        if tipo == "str":
            valores[atributo] = crudo.strip()
        elif tipo == "str_opcional":
            valores[atributo] = crudo.strip() or None
        elif tipo == "int":
            valores[atributo] = _a_int(crudo, variable)
        elif tipo == "float":
            valores[atributo] = _a_float(crudo, variable)
        elif tipo == "bool":
            valores[atributo] = _a_bool(crudo, variable)
        elif tipo == "lista":
            valores[atributo] = tuple(p.strip() for p in crudo.split(",") if p.strip())

    validos = {f.name for f in fields(Configuracion)}
    assert set(valores) <= validos
    return Configuracion(**valores)  # type: ignore[arg-type]
