"""Servidor HTTP multi-hilo ligero para el panel de control web de BTC Whale Intelligence."""

import json
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from sqlalchemy import select, func, desc

from ..configuracion import Configuracion, cargar_configuracion
from ..base_datos.conexion import crear_motor, crear_fabrica_sesiones
from ..base_datos.modelos import (
    EventoAnalizadoORM,
    EntidadORM,
    PrediccionORM,
    ResultadoPrediccionORM,
    VelaMercadoORM,
    TransaccionOnChainORM,
    AtribucionDireccionORM,
    EntradaSalidaORM,
    DireccionORM,
)
from ..clientes_externos.cliente_binance import ClienteBinance
from ..analisis.motor_impacto import MotorImpacto

_logger = logging.getLogger(__name__)
DIRECTORIO_ESTATICOS = Path(__file__).parent / "estaticos"


class ManejadorWeb(SimpleHTTPRequestHandler):
    """Manejador de peticiones para la API REST y los archivos estáticos de la interfaz web."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORIO_ESTATICOS), **kwargs)

    def do_GET(self) -> None:
        url_parseada = urlparse(self.path)
        ruta = url_parseada.path
        params = parse_qs(url_parseada.query)

        if ruta == "/api/salud":
            self._responder_json(self._api_salud())
        elif ruta == "/api/resumen":
            self._responder_json(self._api_resumen())
        elif ruta == "/api/eventos":
            self._responder_json(self._api_eventos(params))
        elif ruta == "/api/entidades":
            self._responder_json(self._api_entidades())
        elif ruta == "/api/predicciones":
            self._responder_json(self._api_predicciones(params))
        else:
            # Archivo estático o SPA fallback
            archivo = DIRECTORIO_ESTATICOS / ruta.lstrip("/")
            if not archivo.exists() or archivo.is_dir():
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        url_parseada = urlparse(self.path)
        if url_parseada.path == "/api/ejecutar-ciclo":
            self._responder_json(self._api_ejecutar_ciclo())
        else:
            self.send_error(404, "Ruta no encontrada")

    def _responder_json(self, datos: Any, codigo: int = 200) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _obtener_sesion(self):
        config = cargar_configuracion()
        motor = crear_motor(config.url_base_datos)
        fabrica = crear_fabrica_sesiones(motor)
        return fabrica()

    def _api_salud(self) -> dict[str, Any]:
        return {"estado": "SALUDABLE", "servicio": "BTC Whale Intelligence", "version": "1.0.0"}

    def _api_resumen(self) -> dict[str, Any]:
        sesion = self._obtener_sesion()
        try:
            config = cargar_configuracion()
            # 1. Precio spot actual y resumen 24h
            precio_btc = 0.0
            volumen_24h_btc = 0.0
            variacion_24h_pct = 0.0
            try:
                binance = ClienteBinance(url_base=config.url_binance)
                resumen = binance.obtener_resumen_24h(config.par_mercado)
                precio_btc = float(resumen.get("precio_actual", 0.0))
                volumen_24h_btc = float(resumen.get("volumen_btc", 0.0))
                variacion_24h_pct = float(resumen.get("cambio_precio_pct", 0.0))
            except Exception as e:
                _logger.warning("No se pudo obtener ticker Binance: %s", e)
                # Fallback a última vela
                ultima_vela = (
                    sesion.query(VelaMercadoORM)
                    .order_by(desc(VelaMercadoORM.marca_tiempo_apertura))
                    .first()
                )
                if ultima_vela:
                    precio_btc = ultima_vela.precio_cierre

            # 2. Conteo de eventos y volumen
            total_eventos = sesion.query(func.count(EventoAnalizadoORM.id)).scalar() or 0
            volumen_total_btc = (
                sesion.query(func.sum(EventoAnalizadoORM.monto_relevante_btc)).scalar() or 0.0
            )

            # 3. Entidades activas
            total_entidades = sesion.query(func.count(EntidadORM.id)).filter_by(activo=True).scalar() or 0
            total_predicciones = sesion.query(func.count(PrediccionORM.id)).scalar() or 0

            return {
                "precio_btc_usd": round(precio_btc, 2),
                "variacion_24h_pct": round(variacion_24h_pct, 2),
                "volumen_24h_btc": round(volumen_24h_btc, 2),
                "total_eventos_detectados": total_eventos,
                "volumen_total_movido_btc": round(volumen_total_btc, 4),
                "volumen_total_usd": round(volumen_total_btc * (precio_btc or 60000.0), 2),
                "total_entidades_vigiladas": total_entidades,
                "total_predicciones_registradas": total_predicciones,
            }
        finally:
            sesion.close()

    def _api_eventos(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        sesion = self._obtener_sesion()
        try:
            limite = int(params.get("limite", ["50"])[0])
            categoria_filtro = params.get("categoria", [None])[0]

            consulta = (
                sesion.query(EventoAnalizadoORM)
                .order_by(desc(EventoAnalizadoORM.marca_tiempo_referencia))
            )
            if categoria_filtro:
                consulta = consulta.filter(EventoAnalizadoORM.categoria_movimiento == categoria_filtro)

            eventos = consulta.limit(limite).all()
            config = cargar_configuracion()
            motor = MotorImpacto(config)
            resultados = []
            for ev in eventos:
                ent_orig = sesion.query(EntidadORM).filter_by(id=ev.entidad_origen_id).first() if ev.entidad_origen_id else None
                ent_dest = sesion.query(EntidadORM).filter_by(id=ev.entidad_destino_id).first() if ev.entidad_destino_id else None

                # Obtener direcciones reales on-chain para origen y destino
                dir_in = None
                dir_out = None
                if ev.transaccion:
                    in_flujo = (
                        sesion.query(EntradaSalidaORM)
                        .filter_by(transaccion_id=ev.transaccion.id, tipo="ENTRADA")
                        .order_by(desc(EntradaSalidaORM.monto_satoshis))
                        .first()
                    )
                    out_flujo = (
                        sesion.query(EntradaSalidaORM)
                        .filter_by(transaccion_id=ev.transaccion.id, tipo="SALIDA")
                        .order_by(desc(EntradaSalidaORM.monto_satoshis))
                        .first()
                    )
                    if in_flujo and in_flujo.direccion_id:
                        d_obj = sesion.query(DireccionORM).filter_by(id=in_flujo.direccion_id).first()
                        if d_obj:
                            dir_in = d_obj.direccion_btc
                    if out_flujo and out_flujo.direccion_id:
                        d_obj = sesion.query(DireccionORM).filter_by(id=out_flujo.direccion_id).first()
                        if d_obj:
                            dir_out = d_obj.direccion_btc

                def resolver_etiqueta(ent, direccion):
                    if ent:
                        return ent.nombre
                    if direccion:
                        return f"Ballena ({direccion[:6]}...{direccion[-4:]})"
                    return "Billetera No Identificada"

                # Calcular señales predictivas cualitativas y cuantitativas
                info_senales = motor.interpretar_senales(ev, ev.caracteristicas)

                resultados.append({
                    "id": ev.id,
                    "txid": ev.transaccion.txid if ev.transaccion else "",
                    "fecha_utc": ev.marca_tiempo_referencia.isoformat() if ev.marca_tiempo_referencia else None,
                    "monto_btc": ev.monto_relevante_btc,
                    "precio_usd": ev.precio_referencia_usd,
                    "valor_usd": round(ev.monto_relevante_btc * (ev.precio_referencia_usd or 0.0), 2),
                    "categoria": ev.categoria_movimiento,
                    "entidad_origen": resolver_etiqueta(ent_orig, dir_in),
                    "entidad_destino": resolver_etiqueta(ent_dest, dir_out),
                    "direccion_origen": dir_in,
                    "direccion_destino": dir_out,
                    "token_origen": info_senales["token_origen"],
                    "token_destino": info_senales["token_destino"],
                    "nota_tokens": info_senales["nota_tokens"],
                    "senales": info_senales["senales"],
                    "senal_24h": info_senales["senales"]["24H"],
                    "senal_7d": info_senales["senales"]["7D"],
                    "senal_30d": info_senales["senales"]["30D"],
                    "nivel_confianza": ev.nivel_confianza,
                    "evidencia": ev.evidencia,
                    "limitaciones": ev.limitaciones,
                })
            return resultados
        finally:
            sesion.close()

    def _api_entidades(self) -> list[dict[str, Any]]:
        sesion = self._obtener_sesion()
        try:
            entidades = sesion.query(EntidadORM).filter_by(activo=True).order_by(EntidadORM.nombre).all()
            res = []
            for e in entidades:
                conteo_dirs = sesion.query(func.count(AtribucionDireccionORM.id)).filter_by(entidad_id=e.id).scalar() or 0
                res.append({
                    "id": e.id,
                    "nombre": e.nombre,
                    "categoria": e.categoria,
                    "nivel_confianza": e.nivel_confianza,
                    "fuentes": e.fuentes_identificacion,
                    "total_direcciones": conteo_dirs,
                    "umbral_btc": e.umbral_personalizado_btc,
                })
            return res
        finally:
            sesion.close()

    def _api_predicciones(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        sesion = self._obtener_sesion()
        try:
            preds = (
                sesion.query(PrediccionORM)
                .order_by(desc(PrediccionORM.marca_tiempo_registro))
                .limit(50)
                .all()
            )
            res = []
            for p in preds:
                resultado_info = None
                if p.resultado:
                    resultado_info = {
                        "estado": p.resultado.estado_resultado,
                        "precio_final_usd": p.resultado.precio_final_usd,
                        "retorno_real_pct": p.resultado.retorno_real_pct,
                        "resultado_categoria": p.resultado.resultado_categoria,
                        "baseline_buy_hold_pct": p.resultado.retorno_baseline_buy_hold_pct,
                        "baseline_persistencia_pct": p.resultado.retorno_baseline_persistencia_pct,
                    }
                res.append({
                    "id": p.id,
                    "evento_id": p.evento_id,
                    "horizonte": p.horizonte,
                    "tipo_estimacion": p.tipo_estimacion,
                    "precio_inicial_usd": p.precio_inicial_usd,
                    "fecha_registro_utc": p.marca_tiempo_registro.isoformat() if p.marca_tiempo_registro else None,
                    "fecha_vencimiento_utc": p.fecha_vencimiento_utc.isoformat() if p.fecha_vencimiento_utc else None,
                    "razon_indeterminacion": p.razon_indeterminacion,
                    "resultado": resultado_info,
                })
            return res
        finally:
            sesion.close()

    def _api_ejecutar_ciclo(self) -> dict[str, Any]:
        """Dispara un ciclo de monitoreo on-demand desde la web."""
        try:
            import argparse
            from ..cli import comando_ejecutar_ciclo_monitoreo
            args = argparse.Namespace()
            codigo = comando_ejecutar_ciclo_monitoreo(args)
            return {"exito": codigo == 0, "mensaje": "Ciclo de monitoreo completado exitosamente"}
        except Exception as e:
            _logger.error("Error al ejecutar ciclo on-demand: %s", e)
            return {"exito": False, "error": str(e)}


def iniciar_servidor_web(host: str = "127.0.0.1", puerto: int = 8000) -> None:
    """Inicia el servidor web en el host y puerto indicados."""
    DIRECTORIO_ESTATICOS.mkdir(parents=True, exist_ok=True)
    servidor = ThreadingHTTPServer((host, puerto), ManejadorWeb)
    print(f"\n=======================================================")
    print(f"[BTC Whale Intelligence] Panel Web")
    print(f"[OK] Servidor activo en: http://{host}:{puerto}")
    print(f"Presiona CTRL + C para detener el servidor")
    print(f"=======================================================\n")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Deteniendo servidor web...")
        servidor.server_close()
