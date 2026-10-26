from datetime import datetime, timedelta, timezone
from btc_whale_intelligence.analisis.caracteristicas import ExtractorCaracteristicas
from btc_whale_intelligence.base_datos.modelos import EventoAnalizadoORM, TransaccionOnChainORM
from btc_whale_intelligence.mercado.sincronizador_mercado import SincronizadorMercado


def test_enriquecimiento_caracteristicas_mercado(sesion, config):
    sincronizador = SincronizadorMercado(sesion, config)
    t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    # Inyectar velas históricas de 1h para las 24h previas
    velas_hist = []
    for h in range(48, -1, -1):
        t_ap = t0 - timedelta(hours=h)
        velas_hist.append(
            {
                "par": "BTCUSDT",
                "intervalo": "1h",
                "marca_tiempo_apertura": t_ap,
                "marca_tiempo_cierre": t_ap + timedelta(hours=1),
                "precio_apertura": 60000.0 + h * 10,
                "precio_maximo": 60500.0 + h * 10,
                "precio_minimo": 59900.0 + h * 10,
                "precio_cierre": 60000.0 + h * 10,
                "volumen_btc": 100.0,
                "volumen_usdt": 6000000.0,
                "conteo_operaciones": 500,
            }
        )
    sincronizador.persistir_velas(velas_hist)

    # Crear transacción y evento en t0
    tx = TransaccionOnChainORM(
        txid="e" * 64,
        marca_tiempo_utc=t0,
        total_entrada_satoshis=100_000_000_000,
        total_salida_satoshis=100_000_000_000,
        comision_satoshis=10000,
        tamano_bytes=250,
        peso_vbytes=200,
    )
    sesion.add(tx)
    sesion.flush()

    evento = EventoAnalizadoORM(
        transaccion_id=tx.id,
        monto_relevante_btc=1000.0,
        monto_total_salidas_btc=1000.0,
        umbral_aplicado_btc=500.0,
        categoria_movimiento="ENTRADA_EXCHANGE",
        nivel_confianza=0.95,
        evidencia="Flujo exchange",
        limitaciones="Sin presuncion de venta",
        marca_tiempo_referencia=t0,
    )
    sesion.add(evento)
    sesion.flush()

    extractor = ExtractorCaracteristicas(sesion, sincronizador)
    caracteristica = extractor.extraer_y_persistir(evento)

    assert caracteristica.precio_referencia_usd is not None
    assert caracteristica.precio_referencia_usd == 60000.0
    assert caracteristica.volatilidad_historica_7d is not None
    assert caracteristica.variacion_precio_24h_pct is not None
    assert evento.estado_procesamiento == "ENRIQUECIDO"
