"""Módulo de notificaciones, despacho SMTP y plantillas de correo."""

from btc_whale_intelligence.notificaciones.despachador_smtp import (
    AlertaMensaje,
    DespachadorSMTP,
    ResultadoEnvio,
)
from btc_whale_intelligence.notificaciones.plantillas_correo import (
    DISCLAIMER_TEXTO,
    generar_plantilla_error_critico,
    generar_plantilla_movimiento,
    generar_plantilla_reporte_diario,
)
from btc_whale_intelligence.notificaciones.reporte_diario import ServicioReporteDiario

__all__ = [
    "AlertaMensaje",
    "ResultadoEnvio",
    "DespachadorSMTP",
    "DISCLAIMER_TEXTO",
    "generar_plantilla_movimiento",
    "generar_plantilla_reporte_diario",
    "generar_plantilla_error_critico",
    "ServicioReporteDiario",
]
