"""Prueba de integración de extremo a extremo (E2E) simulando el flujo completo del sistema.

Valida el ciclo completo de vida:
1. Inicialización de base de datos e importación de entidades.
2. Detección on-chain y clasificación objetiva (sin inferencia de compra/venta).
3. Enriquecimiento con contexto de mercado y características.
4. Pre-registro inmutable de predicciones con horizontes 24H, 7D y 30D.
5. Despacho de alertas SMTP con verificación de idempotencia y aviso legal.
6. Cierre de horizonte y evaluación retrospectiva frente a Buy & Hold y persistencia.
7. Generación y despacho del informe diario consolidado.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from btc_whale_intelligence.analisis.caracteristicas import ExtractorCaracteristicas
from btc_whale_intelligence.analisis.evaluador_historico import EvaluadorHistorico
from btc_whale_intelligence.analisis.motor_impacto import MotorImpacto
from btc_whale_intelligence.analisis.prerregistro import ServicioPrerregistro
from btc_whale_intelligence.mercado.sincronizador_mercado import SincronizadorMercado
from btc_whale_intelligence.base_datos.inicializador import inicializar_base_datos
from btc_whale_intelligence.base_datos.modelos import (
    Base,
    AlertaDespachadaORM,
    EventoAnalizadoORM,
    PrediccionORM,
    ResultadoPrediccionORM,
    VelaMercadoORM,
)
from btc_whale_intelligence.clasificador.motor_clasificacion import MotorClasificacion
from btc_whale_intelligence.configuracion import Configuracion
from btc_whale_intelligence.entidades.servicio_entidades import ServicioEntidades
from btc_whale_intelligence.notificaciones.despachador_smtp import DespachadorSMTP
from btc_whale_intelligence.notificaciones.plantillas_correo import generar_plantilla_movimiento
from btc_whale_intelligence.notificaciones.reporte_diario import ServicioReporteDiario
from btc_whale_intelligence.onchain.colector_bloques import ColectorBloques


@pytest.fixture
def configuracion_prueba():
    return Configuracion(
        url_base_datos="sqlite:///:memory:",
        umbral_exchange_btc=500.0,
        umbral_institucional_btc=250.0,
        umbral_desconocido_btc=1000.0,
        alertas_habilitadas=True,
        smtp_host="smtp.ejemplo.com",
        smtp_puerto=587,
        smtp_remitente="alertas@whalewatcher.local",
        destinatarios_alerta=("analista@ejemplo.com",),
        smtp_starttls=False,
        smtp_ssl=False,
    )


def test_flujo_e2e_completo(configuracion_prueba):
    t0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Base de datos e inicialización
    engine = create_engine(configuracion_prueba.url_base_datos)
    inicializar_base_datos(engine)
    Fabrica = sessionmaker(bind=engine)
    sesion = Fabrica()

    # 2. Catálogo de entidades
    servicio_entidades = ServicioEntidades(sesion)
    entidad_binance = servicio_entidades.registrar_entidad(
        nombre="Binance Exchange",
        categoria="Exchange",
        nivel_confianza=0.98,
        fuentes_identificacion="Prueba E2E",
    )
    servicio_entidades.atribuir_direccion(
        direccion_btc="1BinanceDepositAddressXXXXX",
        nombre_entidad=entidad_binance.nombre,
        grado_certeza=0.98,
        fuente_atribucion="Clustering",
        fecha_verificacion=t0.date(),
        formato="P2PKH",
    )

    # 3. Contexto de mercado histórico previo (velas 1h y vela 1m exacta en t0)
    vela_actual = VelaMercadoORM(
        fuente="Binance",
        par="BTCUSDT",
        intervalo="1m",
        marca_tiempo_apertura=t0,
        marca_tiempo_cierre=t0 + timedelta(minutes=1),
        precio_apertura=60000.0,
        precio_maximo=60050.0,
        precio_minimo=59950.0,
        precio_cierre=60000.0,
        volumen_btc=100.0,
        volumen_usdt=6000000.0,
        conteo_operaciones=200,
    )
    sesion.add(vela_actual)

    velas = [
        VelaMercadoORM(
            fuente="Binance",
            par="BTCUSDT",
            intervalo="1h",
            marca_tiempo_apertura=t0 - timedelta(hours=i),
            marca_tiempo_cierre=t0 - timedelta(hours=i - 1),
            precio_apertura=60000.0,
            precio_maximo=61000.0,
            precio_minimo=59000.0,
            precio_cierre=60000.0 + i * 10,
            volumen_btc=5000.0,
            volumen_usdt=300000000.0,
            conteo_operaciones=1000,
        )
        for i in range(1, 25)
    ]
    for v in velas:
        sesion.add(v)
    sesion.commit()

    # 4. Ingesta On-Chain simulada: bloque con una transacción ballena
    mock_cliente_mempool = MagicMock()
    mock_cliente_mempool.obtener_altura_punta.return_value = 890001
    mock_cliente_mempool.obtener_hash_bloque.return_value = "hash_bloque_890001"
    mock_cliente_mempool.obtener_bloque.return_value = {
        "id": "hash_bloque_890001",
        "height": 890001,
        "timestamp": int(t0.timestamp()),
        "tx_count": 1,
    }

    mock_cliente_mempool.obtener_transacciones_direccion.return_value = []

    # Transacción: 1500 BTC entran a dirección de Binance
    mock_cliente_mempool.obtener_todas_transacciones_bloque.return_value = [
        {
            "txid": "tx_ballena_e2e_001",
            "version": 2,
            "locktime": 0,
            "vin": [
                {
                    "txid": "tx_prev_000",
                    "vout": 0,
                    "prevout": {
                        "scriptpubkey_address": "bc1qdesconocidoorigenXXXXX",
                        "value": 150_000_100_000,  # ~1500 BTC
                    },
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1BinanceDepositAddressXXXXX",
                    "value": 150_000_000_000,  # 1500 BTC exactos a Binance
                },
                {
                    "scriptpubkey_address": "bc1qdesconocidocambioXXXX",
                    "value": 100_000,
                },
            ],
            "size": 250,
            "weight": 1000,
            "fee": 100_000,
            "status": {
                "confirmed": True,
                "block_height": 890001,
                "block_hash": "hash_bloque_890001",
                "block_time": int(t0.timestamp()),
            },
        }
    ]

    colector = ColectorBloques(sesion=sesion, config=configuracion_prueba, cliente_mempool=mock_cliente_mempool)
    eventos = colector.sincronizar()
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.monto_relevante_btc == pytest.approx(1500.0, abs=0.01)

    # 5. Clasificación y extracción de características
    assert evento.categoria_movimiento == "ENTRADA_EXCHANGE"
    assert "no equivale necesariamente a una venta" in evento.limitaciones.lower()

    sincronizador_mercado = SincronizadorMercado(sesion, configuracion_prueba)
    extractor = ExtractorCaracteristicas(sesion, sincronizador_mercado)
    caracteristicas = extractor.extraer_y_persistir(evento)
    assert caracteristicas.precio_referencia_usd is not None

    # 6. Motor probabilístico y pre-registro inmutable (v1: Indeterminado)
    analizador = MotorImpacto(configuracion_prueba)
    prerregistro = ServicioPrerregistro(sesion, analizador)
    predicciones = prerregistro.prerregistrar_evento(evento, caracteristicas)
    assert len(predicciones) == 3
    sesion.commit()

    # Verificar inmutabilidad: no se pueden modificar predicciones
    pred_primera = predicciones[0]
    pred_primera.evidencia = "MODIFICACIÓN_PROHIBIDA"
    with pytest.raises(Exception):
        sesion.flush()
    sesion.rollback()

    # 7. Despacho SMTP de alerta con idempotencia
    despachador = DespachadorSMTP(configuracion_prueba, sesion)
    datos_plantilla = {
        "monto_btc": evento.monto_relevante_btc,
        "categoria": evento.categoria_movimiento,
        "txid": evento.transaccion.txid,
        "precio_usd": evento.precio_referencia_usd,
        "valor_usd": evento.monto_relevante_btc * (evento.precio_referencia_usd or 60000.0),
        "entidad_origen": "Desconocido",
        "entidad_destino": "Binance Exchange",
        "nivel_confianza": evento.nivel_confianza,
        "evidencia": evento.evidencia,
        "limitaciones": evento.limitaciones,
        "estimaciones": [{"horizonte": "24H", "estado": "INDETERMINADA", "razon": "v1"}],
    }
    asunto, txt, html = generar_plantilla_movimiento(datos_plantilla, configuracion_prueba.url_explorador_tx)

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        # Primer envío exitoso
        envios1 = despachador.despachar_a_destinatarios(asunto, txt, html, "MOVIMIENTO_RELEVANTE", evento_id=evento.id)
        assert len(envios1) == 1
        assert envios1[0].exito is True
        assert envios1[0].ya_enviado is False
        assert mock_servidor.send_message.call_count == 1

        # Segundo intento no re-despacha (idempotente)
        envios2 = despachador.despachar_a_destinatarios(asunto, txt, html, "MOVIMIENTO_RELEVANTE", evento_id=evento.id)
        assert len(envios2) == 1
        assert envios2[0].ya_enviado is True
        assert mock_servidor.send_message.call_count == 1

    # 8. Cierre retrospectivo de horizonte (simular paso de 24h)
    precio_cierre_24h = 63000.0  # +5%
    sincronizador_mock = MagicMock()
    sincronizador_mock.obtener_precio_cercano.return_value = (precio_cierre_24h, t0 + timedelta(hours=24))

    evaluador = EvaluadorHistorico(sesion, configuracion_prueba, sincronizador_mock)
    # Ajustamos la marca temporal para evaluar el horizonte 24H vencido
    momento_evaluacion = t0 + timedelta(hours=25)
    resultados = evaluador.evaluar_predicciones_vencidas(ahora=momento_evaluacion)

    assert len(resultados) >= 1
    res_24h = next(r for r in resultados if r.prediccion.horizonte == "24H")
    assert res_24h.estado_resultado == "EVALUADO"
    assert res_24h.retorno_real_pct == pytest.approx(5.0, rel=1e-2)
    assert res_24h.resultado_categoria == "ALCISTA"
    # Principio VIII: Comparación obligatoria con ambos baselines
    assert res_24h.retorno_baseline_buy_hold_pct == pytest.approx(5.0, rel=1e-2)
    assert res_24h.retorno_baseline_persistencia_pct == 0.0

    # 9. Informe diario consolidado
    servicio_reporte = ServicioReporteDiario(configuracion_prueba, sesion)
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        res_rep = servicio_reporte.generar_y_enviar(fecha=t0.date())
        assert res_rep["exito"] is True
        assert res_rep["total_eventos"] == 1
        assert res_rep["volumen_total_btc"] == pytest.approx(1500.0, abs=0.01)
        assert res_rep["despachos_exitosos"] == 1

    sesion.close()
