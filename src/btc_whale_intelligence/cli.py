"""Interfaz de línea de comandos (CLI) principal para BTC Whale Intelligence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .base_datos.conexion import crear_fabrica_sesiones, crear_motor, sesion_transaccional
from .base_datos.inicializador import inicializar_base_datos
from .configuracion import cargar_configuracion
from .entidades.importador_semillas import importar_desde_csv, importar_desde_json
from .observabilidad import configurar_logging


def comando_inicializar_bd(args: argparse.Namespace) -> int:
    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    tablas = inicializar_base_datos(motor)
    print(f"[OK] Base de datos inicializada ({config.url_base_datos}).")
    print(f"[OK] Tablas ({len(tablas)}): {', '.join(tablas)}")
    return 0


def comando_importar_entidades(args: argparse.Namespace) -> int:
    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    ruta = Path(args.archivo)
    if not ruta.exists():
        print(f"[ERROR] Archivo no encontrado: {ruta}", file=sys.stderr)
        return 1

    with sesion_transaccional(fabrica) as sesion:
        if ruta.suffix.lower() == ".json":
            res = importar_desde_json(sesion, ruta)
        else:
            res = importar_desde_csv(sesion, ruta)

    print(f"[OK] Importación completada desde {ruta.name}:")
    print(f"     Entidades procesadas: {res.entidades_procesadas}")
    print(f"     Direcciones procesadas: {res.direcciones_procesadas}")
    print(f"     Atribuciones creadas: {res.atribuciones_creadas}")
    if res.filas_con_error > 0:
        print(f"[AVISO] Errores ({res.filas_con_error}):")
        for err in res.errores[:5]:
            print(f"       - {err}")
    return 0


def comando_sincronizar_onchain(args: argparse.Namespace) -> int:
    from .onchain.colector_bloques import ColectorBloques

    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    with sesion_transaccional(fabrica) as sesion:
        colector = ColectorBloques(sesion, config)
        eventos = colector.sincronizar()

    print(f"[OK] Sincronización on-chain completada. Nuevos movimientos relevantes: {len(eventos)}")
    for ev in eventos:
        print(f"     - Evento #{ev.id}: {ev.monto_relevante_btc:.2f} BTC | {ev.categoria_movimiento} | Confianza: {ev.nivel_confianza:.2f}")
    return 0


def comando_sincronizar_mercado(args: argparse.Namespace) -> int:
    from .mercado.sincronizador_mercado import SincronizadorMercado

    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    with sesion_transaccional(fabrica) as sesion:
        sincronizador = SincronizadorMercado(sesion, config)
        resultados = sincronizador.sincronizar_velas_recientes()

    print(f"[OK] Sincronización de mercado completada ({config.par_mercado}):")
    for intervalo, conteo in resultados.items():
        print(f"     - Intervalo {intervalo}: {conteo} velas actualizadas")
    return 0


def comando_evaluar_predicciones(args: argparse.Namespace) -> int:
    from .analisis.evaluador_historico import EvaluadorHistorico
    from .mercado.sincronizador_mercado import SincronizadorMercado

    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    with sesion_transaccional(fabrica) as sesion:
        sincronizador = SincronizadorMercado(sesion, config)
        evaluador = EvaluadorHistorico(sesion, config, sincronizador)
        resultados = evaluador.evaluar_predicciones_vencidas()

    print(f"[OK] Evaluación retrospectiva completada. Predicciones evaluadas: {len(resultados)}")
    for r in resultados:
        print(f"     - Predicción #{r.prediccion_id}: Retorno real {r.retorno_real_pct:.2f}% | Categoría: {r.resultado_categoria}")
        print(f"       * Baseline Buy & Hold: {r.retorno_baseline_buy_hold_pct:.2f}%")
        print(f"       * Baseline Persistencia: {r.retorno_baseline_persistencia_pct:.2f}% (Error: {r.error_absoluto_persistencia_pct:.2f}%)")
    return 0


def comando_enviar_reporte_diario(args: argparse.Namespace) -> int:
    from datetime import date
    from .notificaciones.reporte_diario import ServicioReporteDiario

    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    fecha_obj = None
    if getattr(args, "fecha", None):
        fecha_obj = date.fromisoformat(args.fecha)

    with sesion_transaccional(fabrica) as sesion:
        servicio = ServicioReporteDiario(config, sesion)
        resultado = servicio.generar_y_enviar(fecha=fecha_obj)

    print(f"[OK] Reporte diario procesado para la fecha: {resultado['fecha']}")
    print(f"     - Total eventos consolidados: {resultado['total_eventos']}")
    print(f"     - Volumen total analizado: {resultado['volumen_total_btc']:.4f} BTC")
    print(f"     - Despachos exitosos: {resultado['despachos_exitosos']}")
    print(f"     - Despachos omitidos (idempotencia previa): {resultado['despachos_ya_enviados']}")
    if resultado['despachos_fallidos'] > 0:
        print(f"     [!] Despachos fallidos: {resultado['despachos_fallidos']}")
        return 1
    return 0


def comando_ejecutar_ciclo_monitoreo(args: argparse.Namespace) -> int:
    from .analisis.caracteristicas import ExtractorCaracteristicas
    from .analisis.motor_impacto import MotorImpacto
    from .analisis.prerregistro import ServicioPrerregistro
    from .clasificador.motor_clasificacion import MotorClasificacion
    from .clientes_externos.cliente_mempool import ClienteMempool
    from .mercado.sincronizador_mercado import SincronizadorMercado
    from .notificaciones.despachador_smtp import DespachadorSMTP
    from .notificaciones.plantillas_correo import generar_plantilla_movimiento
    from .onchain.colector_bloques import ColectorBloques
    from .base_datos.modelos import EntidadORM

    config = cargar_configuracion()
    configurar_logging(config)
    motor = crear_motor(config.url_base_datos)
    inicializar_base_datos(motor)
    fabrica = crear_fabrica_sesiones(motor)

    with sesion_transaccional(fabrica) as sesion:
        print("[1/4] Sincronizando datos de mercado (Binance Spot)...")
        sincronizador_mercado = SincronizadorMercado(sesion, config)
        res_velas = sincronizador_mercado.sincronizar_velas_recientes(par=config.par_mercado, intervalos=("1m", "1h", "1d"))
        velas_sincronizadas = sum(res_velas.values())
        print(f"      Velas sincronizadas: {velas_sincronizadas} ({res_velas})")

        print("[2/4] Consultando mempool y bloques recientes en Bitcoin on-chain...")
        cliente_mempool = ClienteMempool(
            url_primaria=config.url_mempool,
            url_respaldo=config.url_esplora_respaldo,
            intervalo_min_seg=config.onchain_intervalo_min_seg,
        )
        colector = ColectorBloques(sesion=sesion, config=config, cliente_mempool=cliente_mempool)
        eventos = colector.sincronizar()
        print(f"      Eventos relevantes detectados: {len(eventos)}")

        print("[3/4] Extrayendo características y pre-registrando predicciones...")
        extractor = ExtractorCaracteristicas(sesion, sincronizador_mercado)
        analizador = MotorImpacto(config)
        prerregistro = ServicioPrerregistro(sesion, analizador)
        despachador = DespachadorSMTP(config, sesion)

        alertas_despachadas = 0
        for evento in eventos:
            caracteristicas = extractor.extraer_y_persistir(evento)
            prerregistro.prerregistrar_evento(evento, caracteristicas)
            estimaciones = analizador.generar_estimaciones(evento, caracteristicas)

            # Notificaciones si procede
            if config.alertas_habilitadas and config.smtp_configurado():
                origen_nombre = "Desconocido"
                destino_nombre = "Desconocido"
                if evento.entidad_origen_id:
                    ent_orig = sesion.query(EntidadORM).filter_by(id=evento.entidad_origen_id).first()
                    if ent_orig:
                        origen_nombre = ent_orig.nombre
                if evento.entidad_destino_id:
                    ent_dest = sesion.query(EntidadORM).filter_by(id=evento.entidad_destino_id).first()
                    if ent_dest:
                        destino_nombre = ent_dest.nombre

                datos_plantilla = {
                    "monto_btc": evento.monto_relevante_btc,
                    "categoria": evento.categoria_movimiento,
                    "txid": evento.transaccion.txid,
                    "precio_usd": evento.precio_referencia_usd,
                    "valor_usd": (evento.monto_relevante_btc * evento.precio_referencia_usd) if evento.precio_referencia_usd else None,
                    "entidad_origen": origen_nombre,
                    "entidad_destino": destino_nombre,
                    "nivel_confianza": evento.nivel_confianza,
                    "evidencia": evento.evidencia,
                    "limitaciones": evento.limitaciones,
                    "estimaciones": [
                        {"horizonte": e.horizonte, "estado": e.tipo_estimacion, "razon": e.razon_indeterminacion}
                        for e in estimaciones
                    ],
                }
                asunto, txt, html = generar_plantilla_movimiento(datos_plantilla, config.url_explorador_tx)
                envios = despachador.despachar_a_destinatarios(asunto=asunto, cuerpo_texto=txt, cuerpo_html=html, tipo_alerta="MOVIMIENTO_RELEVANTE", evento_id=evento.id)
                alertas_despachadas += sum(1 for r in envios if r.exito and not r.ya_enviado)

        print(f"[4/4] Notificaciones despachadas: {alertas_despachadas}")
        print(f"[OK] Ciclo de monitoreo completado con éxito.")
    return 0


def comando_verificar_salud(args: argparse.Namespace) -> int:
    from sqlalchemy import text
    from .clientes_externos.cliente_mempool import ClienteMempool
    from .clientes_externos.cliente_binance import ClienteBinance

    config = cargar_configuracion()
    print("=== DIAGNÓSTICO DE SALUD OPERATIVA (BTC Whale Intelligence) ===")
    errores = 0

    # 1. Base de datos
    try:
        motor = crear_motor(config.url_base_datos)
        with motor.connect() as conn:
            wal = conn.execute(text("PRAGMA journal_mode;")).scalar()
            integ = conn.execute(text("PRAGMA integrity_check;")).scalar()
            print(f"[OK] Base de datos SQLite conectada (Modo WAL: {wal}, Integridad: {integ})")
    except Exception as exc:
        print(f"[FALLO] Error al verificar SQLite: {exc}")
        errores += 1

    # 2. API Mempool
    try:
        mempool = ClienteMempool(url_primaria=config.url_mempool, url_respaldo=config.url_esplora_respaldo)
        altura = mempool.obtener_altura_punta()
        print(f"[OK] API Mempool.space disponible (Altura de punta: {altura})")
    except Exception as exc:
        print(f"[FALLO] Error al consultar Mempool: {exc}")
        errores += 1

    # 3. API Binance
    try:
        binance = ClienteBinance(url_base=config.url_binance)
        precio = binance.obtener_precio_actual(config.par_mercado)
        print(f"[OK] API Binance Spot disponible (Precio {config.par_mercado}: ${precio:,.2f} USD)")
    except Exception as exc:
        print(f"[FALLO] Error al consultar Binance: {exc}")
        errores += 1

    # 4. Configuración SMTP
    if config.smtp_configurado():
        print(f"[OK] Configuración SMTP presente (Host: {config.smtp_host}:{config.smtp_puerto}, Destinatarios: {len(config.destinatarios_alerta)})")
    else:
        print("[AVISO] Configuración SMTP incompleta o deshabilitada (no se enviarán correos)")

    if errores == 0:
        print(">>> Estado general del sistema: SALUDABLE (0 fallos)")
        return 0
    else:
        print(f">>> Estado general del sistema: DEGRADADO ({errores} fallos detectados)")
        return 1


def comando_servidor_web(args: argparse.Namespace) -> int:
    from .web.servidor import iniciar_servidor_web

    config = cargar_configuracion()
    configurar_logging(config)
    host = getattr(args, "host", "127.0.0.1")
    puerto = int(getattr(args, "puerto", 8000))
    iniciar_servidor_web(host=host, puerto=puerto)
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="btc-whale",
        description="BTC Whale Intelligence - Plataforma de análisis on-chain de Bitcoin.",
    )
    subparsers = parser.add_subparsers(dest="comando", help="Comando a ejecutar")

    # inicializar-bd
    p_init = subparsers.add_parser("inicializar-bd", help="Crea las tablas de la base de datos.")
    p_init.set_defaults(funcion=comando_inicializar_bd)

    # importar-entidades
    p_import = subparsers.add_parser("importar-entidades", help="Importa entidades y direcciones desde CSV o JSON.")
    p_import.add_argument("archivo", help="Ruta al archivo CSV o JSON con entidades.")
    p_import.set_defaults(funcion=comando_importar_entidades)

    # sincronizar-onchain
    p_onchain = subparsers.add_parser("sincronizar-onchain", help="Sincroniza bloques y mempool on-chain detectando movimientos.")
    p_onchain.set_defaults(funcion=comando_sincronizar_onchain)

    # sincronizar-mercado
    p_mercado = subparsers.add_parser("sincronizar-mercado", help="Sincroniza cotizaciones y velas de BTC/USDT desde Binance.")
    p_mercado.set_defaults(funcion=comando_sincronizar_mercado)

    # evaluar-predicciones
    p_eval = subparsers.add_parser("evaluar-predicciones", help="Evalúa retrospectivamente predicciones vencidas contra la realidad y baselines.")
    p_eval.set_defaults(funcion=comando_evaluar_predicciones)

    # enviar-reporte-diario
    p_rep = subparsers.add_parser("enviar-reporte-diario", help="Genera y despacha el reporte diario consolidado.")
    p_rep.add_argument("--fecha", help="Fecha en formato YYYY-MM-DD (por defecto el día de ayer UTC).", default=None)
    p_rep.set_defaults(funcion=comando_enviar_reporte_diario)

    # ejecutar-ciclo-monitoreo
    p_ciclo = subparsers.add_parser("ejecutar-ciclo-monitoreo", help="Ejecuta el ciclo integral de monitoreo on-chain, mercado, análisis y alertas.")
    p_ciclo.set_defaults(funcion=comando_ejecutar_ciclo_monitoreo)

    # verificar-salud
    p_salud = subparsers.add_parser("verificar-salud", help="Diagnostica la conectividad de base de datos, APIs públicas y SMTP.")
    p_salud.set_defaults(funcion=comando_verificar_salud)

    # servidor-web
    p_web = subparsers.add_parser("servidor-web", help="Inicia el servidor y panel de control web en tiempo real.")
    p_web.add_argument("--host", default="127.0.0.1", help="Dirección IP donde escuchar (por defecto 127.0.0.1).")
    p_web.add_argument("--puerto", type=int, default=8000, help="Puerto HTTP del servidor (por defecto 8000).")
    p_web.set_defaults(funcion=comando_servidor_web)

    return parser


def principal(argumentos: Optional[Sequence[str]] = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argumentos)
    if not hasattr(args, "funcion"):
        parser.print_help()
        return 1
    return args.funcion(args)


if __name__ == "__main__":
    sys.exit(principal())
