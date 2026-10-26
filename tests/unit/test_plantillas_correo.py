"""Pruebas unitarias para las plantillas de correo electrónico."""

import pytest
from btc_whale_intelligence.notificaciones.plantillas_correo import (
    generar_plantilla_movimiento,
    generar_plantilla_reporte_diario,
    generar_plantilla_error_critico,
    DISCLAIMER_TEXTO,
)


def test_plantilla_movimiento_contiene_disclaimer_y_enlace():
    datos_evento = {
        "txid": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "categoria": "ENTRADA_EXCHANGE",
        "monto_btc": 1500.5,
        "precio_usd": 65000.0,
        "valor_usd": 1500.5 * 65000.0,
        "entidad_origen": "Ballena Desconocida",
        "entidad_destino": "Binance Hot Wallet",
        "nivel_confianza": 0.85,
        "evidencia": "Cluster de direcciones atribuido a Binance",
        "limitaciones": "No se puede confirmar si es depósito para venta inmediata o garantía colateral",
        "estimaciones": [
            {
                "horizonte": "24H",
                "estado": "INDETERMINADA",
                "razon": "Modelo v1 en calibración sin datos estadísticos fuera de muestra",
            }
        ],
    }

    asunto, texto, html = generar_plantilla_movimiento(datos_evento, url_explorador="https://mempool.space/tx/")

    assert "ALERTA" in asunto
    assert "1,500.5" in asunto or "1500.5" in asunto
    assert "ENTRADA_EXCHANGE" in asunto

    # Texto
    assert "https://mempool.space/tx/abcdef" in texto
    assert DISCLAIMER_TEXTO in texto
    assert "No debe interpretarse automáticamente como compra o venta" in texto
    assert "Binance Hot Wallet" in texto
    assert "INDETERMINADA" in texto

    # HTML
    assert "<html" in html.lower()
    assert "href=\"https://mempool.space/tx/abcdef" in html
    assert "Binance Hot Wallet" in html
    assert "aviso legal" in html.lower() or "disclaimer" in html.lower()


def test_plantilla_reporte_diario():
    datos_reporte = {
        "fecha": "2026-10-26",
        "total_eventos": 5,
        "volumen_total_btc": 12500.0,
        "entidades_activas": [
            {"nombre": "Binance", "flujo_neto_btc": 3200.0, "movimientos": 3},
            {"nombre": "Coinbase", "flujo_neto_btc": -1500.0, "movimientos": 2},
        ],
        "evaluaciones_recientes": [
            {
                "horizonte": "24H",
                "retorno_real_pct": 2.5,
                "resultado_categoria": "ALCISTA",
                "brier_score": None,
                "retorno_buy_hold_pct": 2.5,
            }
        ],
    }

    asunto, texto, html = generar_plantilla_reporte_diario(datos_reporte)

    assert "Informe Diario" in asunto
    assert "2026-10-26" in asunto
    assert "12,500" in texto or "12500" in texto
    assert "Binance" in texto
    assert "Coinbase" in texto
    assert DISCLAIMER_TEXTO in texto
    assert "<table" in html.lower()


def test_plantilla_error_critico():
    asunto, texto, html = generar_plantilla_error_critico(
        componente="ColectorOnChain",
        tipo_error="ConexionRechazada",
        mensaje="No se pudo conectar a mempool.space tras 5 reintentos",
        contexto="Bloque 890120",
    )

    assert "[ERROR CRÍTICO]" in asunto
    assert "ColectorOnChain" in texto
    assert "890120" in texto
    assert "ColectorOnChain" in html
