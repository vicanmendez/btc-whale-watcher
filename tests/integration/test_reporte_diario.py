"""Prueba de integración para la generación y envío del informe diario consolidado."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from btc_whale_intelligence.base_datos.modelos import (
    Base,
    EntidadORM,
    TransaccionOnChainORM,
    EventoAnalizadoORM,
    PrediccionORM,
    ResultadoPrediccionORM,
    AlertaDespachadaORM,
)
from btc_whale_intelligence.configuracion import Configuracion
from btc_whale_intelligence.notificaciones.reporte_diario import ServicioReporteDiario


@pytest.fixture
def sesion_bd():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Fabrica = sessionmaker(bind=engine)
    session = Fabrica()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def configuracion_smtp():
    return Configuracion(
        smtp_host="smtp.ejemplo.com",
        smtp_puerto=587,
        smtp_remitente="alertas@whalewatcher.local",
        destinatarios_alerta=("analista@ejemplo.com",),
        smtp_starttls=False,
        smtp_ssl=False,
    )


def test_generacion_y_envio_reporte_diario(sesion_bd, configuracion_smtp):
    ahora = datetime.now(timezone.utc)

    # Crear entidad
    entidad = EntidadORM(
        nombre="Kraken Exchange",
        categoria="Exchange",
        nivel_confianza=0.95,
        fuentes_identificacion="Arkham",
        activo=True,
    )
    sesion_bd.add(entidad)
    sesion_bd.commit()

    # Crear transaccion y evento
    tx = TransaccionOnChainORM(
        txid="tx_diaria_001",
        tamano_bytes=250,
        peso_vbytes=200,
        bloque_altura=890000,
        bloque_hash="hash_001",
        marca_tiempo_utc=ahora - timedelta(hours=5),
        total_entrada_satoshis=200_000_000_000,
        total_salida_satoshis=199_990_000_000,
        comision_satoshis=10_000_000,
        confirmaciones=1,
    )
    sesion_bd.add(tx)
    sesion_bd.commit()

    evento = EventoAnalizadoORM(
        transaccion_id=tx.id,
        entidad_destino_id=entidad.id,
        monto_relevante_btc=2000.0,
        monto_total_salidas_btc=1999.9,
        umbral_aplicado_btc=500.0,
        categoria_movimiento="ENTRADA_EXCHANGE",
        nivel_confianza=0.95,
        evidencia="Entrada a cluster Kraken",
        limitaciones="Ninguna conocida",
        marca_tiempo_referencia=ahora - timedelta(hours=5),
        precio_referencia_usd=64000.0,
        estado_procesamiento="ANALIZADO",
    )
    sesion_bd.add(evento)
    sesion_bd.commit()

    # Predicción y resultado
    pred = PrediccionORM(
        evento_id=evento.id,
        horizonte="24H",
        tipo_estimacion="INDETERMINADA",
        marca_tiempo_referencia=ahora - timedelta(hours=30),
        marca_tiempo_registro=ahora - timedelta(hours=30),
        fecha_vencimiento_utc=ahora - timedelta(hours=6),
        precio_inicial_usd=62000.0,
        umbral_neutral_pct=1.0,
        razon_indeterminacion="Calibración v1",
        evidencia="v1 calibracion",
        limitaciones="sin inferencia",
        modelo_version="v1.0.0-indeterminado",
        datos_entrada_json="{}",
        hash_contenido="hash_pred_001",
    )
    sesion_bd.add(pred)
    sesion_bd.commit()

    res = ResultadoPrediccionORM(
        prediccion_id=pred.id,
        estado_resultado="EVALUADO",
        precio_final_usd=64000.0,
        marca_tiempo_precio_final=ahora - timedelta(hours=6),
        retorno_real_pct=3.22,
        resultado_categoria="ALCISTA",
        retorno_baseline_buy_hold_pct=3.22,
        retorno_baseline_persistencia_pct=0.0,
    )
    sesion_bd.add(res)
    sesion_bd.commit()

    servicio = ServicioReporteDiario(configuracion_smtp, sesion_bd)

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        resultado = servicio.generar_y_enviar(fecha=ahora.date())

        assert resultado["exito"] is True
        assert resultado["total_eventos"] == 1
        assert resultado["despachos_exitosos"] == 1
        assert mock_servidor.send_message.called

    # Verificar registro en base de datos
    alertas = sesion_bd.query(AlertaDespachadaORM).filter_by(tipo_alerta="INFORME_DIARIO").all()
    assert len(alertas) == 1
    assert alertas[0].estado == "ENVIADO"

    # Segunda ejecución no debe duplicar (idempotencia)
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        resultado2 = servicio.generar_y_enviar(fecha=ahora.date())
        assert resultado2["exito"] is True
        assert resultado2["despachos_ya_enviados"] == 1
        assert not mock_servidor.send_message.called
