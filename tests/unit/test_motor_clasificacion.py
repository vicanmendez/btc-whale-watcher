from datetime import datetime, timezone
import pytest
from btc_whale_intelligence.clasificador.motor_clasificacion import MotorClasificacion
from btc_whale_intelligence.onchain.detector_movimientos import DetectorMovimientos
from btc_whale_intelligence.onchain.parser_transaccion import (
    EntradaParsed,
    SalidaParsed,
    TransaccionParsed,
)


def _crear_tx(entradas, salidas):
    return TransaccionParsed(
        txid="dummy" + "0" * 59,
        bloque_altura=890123,
        bloque_hash="hash",
        marca_tiempo_utc=datetime.now(timezone.utc),
        total_entrada_satoshis=sum(e.monto_satoshis for e in entradas),
        total_salida_satoshis=sum(s.monto_satoshis for s in salidas),
        comision_satoshis=1000,
        tamano_bytes=200,
        peso_vbytes=200,
        confirmaciones=1,
        es_mempool=False,
        entradas=tuple(entradas),
        salidas=tuple(salidas),
    )


def test_clasificacion_prohibe_terminos_compra_venta(sesion, config):
    detector = DetectorMovimientos(sesion, config)
    motor = MotorClasificacion(detector)

    tx = _crear_tx(
        entradas=[EntradaParsed(0, "tx0", 0, "1Origen", 100_000_000_000)],
        salidas=[SalidaParsed(0, "1Destino", 100_000_000_000)],
    )

    calificacion = motor.clasificar(tx)
    assert calificacion.categoria in {
        "TRANSFERENCIA_INTERNA",
        "ENTRADA_EXCHANGE",
        "SALIDA_EXCHANGE",
        "MOVIMIENTO_CORPORATIVO",
        "DESCONOCIDA",
        "INCIERTA",
    }
    assert "COMPRA" not in calificacion.categoria
    assert "VENTA" not in calificacion.categoria
