"""Generador y remitente del informe diario consolidado de entidades, flujos netos y baselines."""

import logging
from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from btc_whale_intelligence.base_datos.modelos import (
    EventoAnalizadoORM,
    EntidadORM,
    ResultadoPrediccionORM,
    PrediccionORM,
)
from btc_whale_intelligence.configuracion import Configuracion
from btc_whale_intelligence.notificaciones.despachador_smtp import DespachadorSMTP
from btc_whale_intelligence.notificaciones.plantillas_correo import generar_plantilla_reporte_diario

_logger = logging.getLogger(__name__)


class ServicioReporteDiario:
    """Consolida las métricas del día (movimientos, flujos y evaluaciones) y despacha el reporte diario."""

    def __init__(self, configuracion: Configuracion, sesion: Session) -> None:
        self._config = configuracion
        self._sesion = sesion
        self._despachador = DespachadorSMTP(configuracion, sesion)

    def compilar_datos_diarios(self, fecha: date) -> dict[str, Any]:
        """Extrae de la base de datos la actividad consolidada de la fecha en UTC."""
        inicio_utc = datetime.combine(fecha, time.min).replace(tzinfo=timezone.utc)
        fin_utc = datetime.combine(fecha, time.max).replace(tzinfo=timezone.utc)

        # 1. Eventos detectados en el período
        eventos = (
            self._sesion.query(EventoAnalizadoORM)
            .filter(
                EventoAnalizadoORM.marca_tiempo_referencia >= inicio_utc,
                EventoAnalizadoORM.marca_tiempo_referencia <= fin_utc,
            )
            .all()
        )

        total_eventos = len(eventos)
        volumen_total_btc = sum(e.monto_relevante_btc for e in eventos)

        # 2. Flujo neto por entidad
        flujos_entidad: dict[int, dict[str, Any]] = {}
        for ev in eventos:
            # Flujo entrante (destino)
            if ev.entidad_destino_id is not None:
                if ev.entidad_destino_id not in flujos_entidad:
                    flujos_entidad[ev.entidad_destino_id] = {"flujo_neto": 0.0, "movs": 0}
                flujos_entidad[ev.entidad_destino_id]["flujo_neto"] += ev.monto_relevante_btc
                flujos_entidad[ev.entidad_destino_id]["movs"] += 1

            # Flujo saliente (origen)
            if ev.entidad_origen_id is not None:
                if ev.entidad_origen_id not in flujos_entidad:
                    flujos_entidad[ev.entidad_origen_id] = {"flujo_neto": 0.0, "movs": 0}
                flujos_entidad[ev.entidad_origen_id]["flujo_neto"] -= ev.monto_relevante_btc
                flujos_entidad[ev.entidad_origen_id]["movs"] += 1

        entidades_activas: list[dict[str, Any]] = []
        for ent_id, info in flujos_entidad.items():
            ent = self._sesion.query(EntidadORM).filter_by(id=ent_id).first()
            nombre = ent.nombre if ent else f"Entidad #{ent_id}"
            entidades_activas.append({
                "nombre": nombre,
                "flujo_neto_btc": round(info["flujo_neto"], 4),
                "movimientos": info["movs"],
            })

        # Ordenar entidades por mayor valor absoluto de flujo
        entidades_activas.sort(key=lambda x: abs(x["flujo_neto_btc"]), reverse=True)

        # 3. Evaluaciones concluidas en el período
        resultados = (
            self._sesion.query(ResultadoPrediccionORM)
            .join(PrediccionORM, ResultadoPrediccionORM.prediccion_id == PrediccionORM.id)
            .filter(
                ResultadoPrediccionORM.evaluado_en >= inicio_utc,
                ResultadoPrediccionORM.evaluado_en <= fin_utc,
            )
            .all()
        )

        evaluaciones_recientes: list[dict[str, Any]] = []
        for res in resultados:
            pred = res.prediccion
            evaluaciones_recientes.append({
                "horizonte": pred.horizonte if pred else "?",
                "retorno_real_pct": res.retorno_real_pct or 0.0,
                "resultado_categoria": res.resultado_categoria or "NEUTRAL",
                "brier_score": res.brier_score,
                "retorno_buy_hold_pct": res.retorno_baseline_buy_hold_pct or 0.0,
            })

        return {
            "fecha": str(fecha),
            "total_eventos": total_eventos,
            "volumen_total_btc": round(volumen_total_btc, 4),
            "entidades_activas": entidades_activas,
            "evaluaciones_recientes": evaluaciones_recientes,
        }

    def generar_y_enviar(self, fecha: Optional[date] = None) -> dict[str, Any]:
        """Compila los datos, genera las plantillas y despacha el reporte por correo electrónico."""
        if fecha is None:
            fecha = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        _logger.info("Generando reporte diario consolidado", extra={"fecha": str(fecha)})

        datos = self.compilar_datos_diarios(fecha)
        asunto, cuerpo_texto, cuerpo_html = generar_plantilla_reporte_diario(datos)

        resultados_envio = self._despachador.despachar_a_destinatarios(
            asunto=asunto,
            cuerpo_texto=cuerpo_texto,
            cuerpo_html=cuerpo_html,
            tipo_alerta="INFORME_DIARIO",
        )

        exitosos = sum(1 for r in resultados_envio if r.exito and not r.ya_enviado)
        ya_enviados = sum(1 for r in resultados_envio if r.ya_enviado)
        fallidos = sum(1 for r in resultados_envio if not r.exito)

        resumen = {
            "exito": fallidos == 0,
            "fecha": str(fecha),
            "total_eventos": datos["total_eventos"],
            "volumen_total_btc": datos["volumen_total_btc"],
            "despachos_exitosos": exitosos,
            "despachos_ya_enviados": ya_enviados,
            "despachos_fallidos": fallidos,
        }

        _logger.info("Proceso de reporte diario finalizado", extra=resumen)
        return resumen
