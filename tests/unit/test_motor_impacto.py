from datetime import datetime, timezone
from btc_whale_intelligence.analisis.motor_impacto import MotorImpacto
from btc_whale_intelligence.base_datos.modelos import CaracteristicaCalculadaORM, EventoAnalizadoORM


def test_motor_impacto_emite_indeterminado_en_v1(config):
    motor = MotorImpacto(config)
    t0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    evento = EventoAnalizadoORM(
        id=1,
        transaccion_id=1,
        monto_relevante_btc=1000.0,
        monto_total_salidas_btc=1000.0,
        umbral_aplicado_btc=500.0,
        categoria_movimiento="ENTRADA_EXCHANGE",
        nivel_confianza=0.95,
        evidencia="Binance deposit",
        limitaciones="No presuncion de venta",
        marca_tiempo_referencia=t0,
    )
    caracteristica = CaracteristicaCalculadaORM(
        id=1,
        evento_id=1,
        precio_referencia_usd=65000.0,
        ratio_monto_volumen_24h=0.02,
    )

    # 1. Capa A
    capa_a = motor.analizar_capa_a_liquidez(caracteristica, evento)
    assert capa_a.ratio_volumen_24h == 0.02
    assert "significativo" in capa_a.evaluacion_liquidez

    # 2. Capa B
    capa_b = motor.analizar_capa_b_asociacion(caracteristica, evento)
    assert not capa_b.asociacion_disponible
    assert "Principio VI" in capa_b.resumen_asociacion

    # 3. Capa C: Estimaciones para 24H, 7D y 30D
    estimaciones = motor.generar_estimaciones(evento, caracteristica)
    assert len(estimaciones) == 3
    for est in estimaciones:
        assert est.tipo_estimacion == "INDETERMINADA"
        assert est.probabilidad_alcista is None
        assert est.probabilidad_bajista is None
        assert est.probabilidad_neutral is None
        assert "Principio" in est.razon_indeterminacion
