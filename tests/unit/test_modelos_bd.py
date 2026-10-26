from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from btc_whale_intelligence.base_datos.conexion import crear_motor
from btc_whale_intelligence.base_datos.inicializador import inicializar_base_datos
from btc_whale_intelligence.base_datos.modelos import (
    AtribucionDireccionORM,
    DireccionORM,
    EntidadORM,
    ErrorPrediccionInmutable,
    EventoAnalizadoORM,
    PrediccionORM,
    TransaccionOnChainORM,
    VelaMercadoORM,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

TABLAS_ESPERADAS = {
    "entidades",
    "direcciones",
    "atribuciones_direcciones",
    "transacciones_onchain",
    "entradas_salidas",
    "saldos_historicos",
    "velas_mercado",
    "eventos_analizados",
    "caracteristicas_calculadas",
    "predicciones",
    "resultados_predicciones",
    "alertas_despachadas",
    "estado_ingesta",
    "errores_operativos",
    "validaciones_modelos",
}


def _tx(txid="a" * 64):
    return TransaccionOnChainORM(
        txid=txid,
        marca_tiempo_utc=T0,
        total_entrada_satoshis=10,
        total_salida_satoshis=9,
        comision_satoshis=1,
        tamano_bytes=200,
        peso_vbytes=150,
    )


def _evento(sesion):
    tx = _tx()
    sesion.add(tx)
    sesion.flush()
    evento = EventoAnalizadoORM(
        transaccion_id=tx.id,
        monto_relevante_btc=600,
        monto_total_salidas_btc=600,
        umbral_aplicado_btc=500,
        categoria_movimiento="DESCONOCIDA",
        nivel_confianza=0.0,
        evidencia="-",
        limitaciones="-",
        marca_tiempo_referencia=T0,
    )
    sesion.add(evento)
    sesion.flush()
    return evento


def _prediccion(evento, **cambios):
    datos = dict(
        evento_id=evento.id,
        horizonte="24H",
        tipo_estimacion="INDETERMINADA",
        marca_tiempo_referencia=T0,
        marca_tiempo_registro=T0,
        fecha_vencimiento_utc=T0 + timedelta(hours=24),
        precio_inicial_usd=50000.0,
        umbral_neutral_pct=1.0,
        razon_indeterminacion="sin modelo validado",
        evidencia="-",
        limitaciones="-",
        modelo_version="v1-indeterminado",
        datos_entrada_json="{}",
        hash_contenido="0" * 64,
    )
    datos.update(cambios)
    return PrediccionORM(**datos)


def test_crea_todas_las_tablas(motor):
    assert TABLAS_ESPERADAS <= set(inicializar_base_datos(motor))


def test_inicializacion_idempotente(motor):
    inicializar_base_datos(motor)
    inicializar_base_datos(motor)


def test_wal_activo_en_archivo(tmp_path):
    motor = crear_motor(f"sqlite:///{tmp_path / 'x.db'}")
    with motor.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
    motor.dispose()


def test_txid_unico(sesion):
    sesion.add(_tx())
    sesion.flush()
    sesion.add(_tx())
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_atribucion_unica_y_con_fuente(sesion):
    e = EntidadORM(nombre="X", categoria="Exchange", nivel_confianza=0.9, fuentes_identificacion="doc")
    d = DireccionORM(direccion_btc="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", formato="P2PKH")
    sesion.add_all([e, d])
    sesion.flush()
    sesion.add(AtribucionDireccionORM(direccion_id=d.id, entidad_id=e.id, grado_certeza=0.9,
                                      fuente_atribucion="  ", fecha_verificacion=date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_categoria_entidad_restringida(sesion):
    sesion.add(EntidadORM(nombre="Y", categoria="Comprador", nivel_confianza=0.5, fuentes_identificacion="doc"))
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_vela_unica(sesion):
    def vela():
        return VelaMercadoORM(intervalo="1m", marca_tiempo_apertura=T0, marca_tiempo_cierre=T0 + timedelta(minutes=1),
                              precio_apertura=1, precio_maximo=1, precio_minimo=1, precio_cierre=1,
                              volumen_btc=1, volumen_usdt=1)
    sesion.add(vela())
    sesion.flush()
    sesion.add(vela())
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_fechas_vuelven_en_utc(sesion):
    sesion.add(_tx())
    sesion.commit()
    sesion.expire_all()
    tx = sesion.query(TransaccionOnChainORM).one()
    assert tx.marca_tiempo_utc == T0 and tx.marca_tiempo_utc.tzinfo is not None


def test_prediccion_indeterminada_no_admite_probabilidades(sesion):
    evento = _evento(sesion)
    sesion.add(_prediccion(evento, probabilidad_alcista=0.5, probabilidad_bajista=0.3, probabilidad_neutral=0.2))
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_prediccion_probabilistica_debe_sumar_uno(sesion):
    evento = _evento(sesion)
    sesion.add(_prediccion(evento, tipo_estimacion="PROBABILISTICA", razon_indeterminacion=None,
                           probabilidad_alcista=0.5, probabilidad_bajista=0.5, probabilidad_neutral=0.5))
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_prediccion_inmutable_por_orm(sesion):
    evento = _evento(sesion)
    p = _prediccion(evento)
    sesion.add(p)
    sesion.commit()
    p.precio_inicial_usd = 1.0
    with pytest.raises(ErrorPrediccionInmutable):
        sesion.flush()
    sesion.rollback()
    sesion.delete(p)
    with pytest.raises(ErrorPrediccionInmutable):
        sesion.flush()


def test_prediccion_inmutable_por_trigger(sesion):
    evento = _evento(sesion)
    sesion.add(_prediccion(evento))
    sesion.commit()
    with pytest.raises(Exception, match="inmutables"):
        sesion.execute(text("UPDATE predicciones SET precio_inicial_usd = 1"))
    sesion.rollback()
    with pytest.raises(Exception, match="inmutables"):
        sesion.execute(text("DELETE FROM predicciones"))
