from datetime import datetime, timedelta, timezone
from btc_whale_intelligence.analisis.caracteristicas import ExtractorCaracteristicas
from btc_whale_intelligence.analisis.evaluador_historico import EvaluadorHistorico
from btc_whale_intelligence.analisis.motor_impacto import MotorImpacto
from btc_whale_intelligence.analisis.prerregistro import ServicioPrerregistro
from btc_whale_intelligence.base_datos.modelos import EventoAnalizadoORM, PrediccionORM, TransaccionOnChainORM
from btc_whale_intelligence.mercado.sincronizador_mercado import SincronizadorMercado


def test_ciclo_completo_prerregistro_y_evaluacion_con_baselines(sesion, config):
    sincronizador = SincronizadorMercado(sesion, config)
    t_evento = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    # 1. Vela en t_evento: $50,000
    sincronizador.persistir_velas(
        [
            {
                "par": "BTCUSDT",
                "intervalo": "1m",
                "marca_tiempo_apertura": t_evento,
                "marca_tiempo_cierre": t_evento + timedelta(minutes=1),
                "precio_apertura": 50000.0,
                "precio_maximo": 50100.0,
                "precio_minimo": 49900.0,
                "precio_cierre": 50000.0,
                "volumen_btc": 10.0,
                "volumen_usdt": 500000.0,
                "conteo_operaciones": 100,
            }
        ]
    )

    # 2. Transacción y evento
    tx = TransaccionOnChainORM(
        txid="p" * 64,
        marca_tiempo_utc=t_evento,
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
        limitaciones="No presuncion de venta",
        marca_tiempo_referencia=t_evento,
    )
    sesion.add(evento)
    sesion.flush()

    # 3. Extraer características
    extractor = ExtractorCaracteristicas(sesion, sincronizador)
    caracteristica = extractor.extraer_y_persistir(evento)

    # 4. Pre-registro inmutable de predicciones
    motor_impacto = MotorImpacto(config)
    servicio_prerregistro = ServicioPrerregistro(sesion, motor_impacto)
    predicciones = servicio_prerregistro.prerregistrar_evento(evento, caracteristica)

    assert len(predicciones) == 3
    pred_24h = [p for p in predicciones if p.horizonte == "24H"][0]
    assert pred_24h.tipo_estimacion == "INDETERMINADA"
    assert pred_24h.precio_inicial_usd == 50000.0
    assert pred_24h.fecha_vencimiento_utc == t_evento + timedelta(hours=24)

    # 5. Inyectar precio final al vencimiento de 24h: $52,000 (+4.00%)
    t_venc_24h = t_evento + timedelta(hours=24)
    sincronizador.persistir_velas(
        [
            {
                "par": "BTCUSDT",
                "intervalo": "1m",
                "marca_tiempo_apertura": t_venc_24h,
                "marca_tiempo_cierre": t_venc_24h + timedelta(minutes=1),
                "precio_apertura": 52000.0,
                "precio_maximo": 52100.0,
                "precio_minimo": 51900.0,
                "precio_cierre": 52000.0,
                "volumen_btc": 20.0,
                "volumen_usdt": 1040000.0,
                "conteo_operaciones": 150,
            }
        ]
    )

    # 6. Ejecutar evaluador retrospectivo
    evaluador = EvaluadorHistorico(sesion, config, sincronizador)
    resultados = evaluador.evaluar_predicciones_vencidas()

    assert len(resultados) >= 1
    res_24h = [r for r in resultados if r.prediccion_id == pred_24h.id][0]

    assert res_24h.estado_resultado == "EVALUADO"
    assert res_24h.precio_final_usd == 52000.0
    assert abs(res_24h.retorno_real_pct - 4.0) < 1e-3
    assert res_24h.resultado_categoria == "ALCISTA"

    # Comparación obligatoria con baselines (Principio VIII)
    assert abs(res_24h.retorno_baseline_buy_hold_pct - 4.0) < 1e-3
    assert res_24h.retorno_baseline_persistencia_pct == 0.0
    assert abs(res_24h.error_absoluto_persistencia_pct - 4.0) < 1e-3
