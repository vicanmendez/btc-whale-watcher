"""Plantillas de correo electrónico responsivas (HTML y texto plano) con disclaimer financiero."""

from typing import Any, Optional


DISCLAIMER_TEXTO = (
    "AVISO LEGAL Y DE RIESGO: Este mensaje es de carácter estrictamente informativo y experimental. "
    "Ninguna transferencia on-chain debe interpretarse automáticamente como una compra o venta. "
    "No constituye asesoramiento financiero ni recomendación de inversión. Las estimaciones son "
    "hipótesis estadísticas sujetas a incertidumbre y riesgo de mercado."
)

ESTILO_BASE_HTML = """
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.5;
    background-color: #f8fafc;
    margin: 0;
    padding: 20px;
"""


def _encabezado_html(titulo: str, subtitulo: str) -> str:
    return f"""
    <div style="background-color: #0f172a; color: #ffffff; padding: 24px; border-radius: 8px 8px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">🐋 BTC Whale Intelligence</h1>
        <p style="margin: 6px 0 0 0; font-size: 14px; color: #94a3b8;">{titulo} &bull; {subtitulo}</p>
    </div>
    """


def _pie_disclaimer_html() -> str:
    return f"""
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 14px; margin-top: 24px; font-size: 12px; color: #991b1b; line-height: 1.4;">
        <strong>⚠️ AVISO LEGAL Y METODOLÓGICO:</strong><br>
        {DISCLAIMER_TEXTO}
    </div>
    <div style="text-align: center; margin-top: 18px; font-size: 11px; color: #64748b;">
        Plataforma BTC Whale Intelligence &bull; Ejecución local auditable &bull; Código Abierto
    </div>
    """


def generar_plantilla_movimiento(
    datos_evento: dict[str, Any],
    url_explorador: str = "https://mempool.space/tx/",
) -> tuple[str, str, str]:
    """Genera (asunto, texto_plano, html) para una alerta de movimiento relevante."""
    monto_btc = datos_evento.get("monto_btc", 0.0)
    categoria = datos_evento.get("categoria", "DESCONOCIDA")
    txid = datos_evento.get("txid", "")
    enlace_tx = f"{url_explorador.rstrip('/')}/{txid}"
    precio_usd = datos_evento.get("precio_usd")
    valor_usd = datos_evento.get("valor_usd")
    entidad_origen = datos_evento.get("entidad_origen", "No identificada")
    entidad_destino = datos_evento.get("entidad_destino", "No identificada")
    confianza = datos_evento.get("nivel_confianza", 0.0)
    evidencia = datos_evento.get("evidencia", "Sin evidencia documentada")
    limitaciones = datos_evento.get("limitaciones", "Sin limitaciones registradas")
    estimaciones = datos_evento.get("estimaciones", [])

    asunto = f"[ALERTA] Movimiento de {monto_btc:,.1f} BTC ({categoria})"

    # Texto plano
    lineas_texto = [
        f"=== BTC WHALE INTELLIGENCE: ALERTA DE MOVIMIENTO ===",
        f"Categoría: {categoria}",
        f"Monto Relevante: {monto_btc:,.4f} BTC",
    ]
    if valor_usd is not None and precio_usd is not None:
        lineas_texto.append(f"Valor Estimado: ${valor_usd:,.2f} USD (@ ${precio_usd:,.2f})")
    lineas_texto.extend([
        f"Origen: {entidad_origen}",
        f"Destino: {entidad_destino}",
        f"Confianza de Atribución: {confianza * 100:.1f}%",
        f"Transacción (TxID): {txid}",
        f"Explorador: {enlace_tx}",
        "",
        "--- EVIDENCIA OBSERVADA ---",
        evidencia,
        "",
        "--- LIMITACIONES COGNITIVAS Y SESGOS ---",
        limitaciones,
        "Principio metodológico: No debe interpretarse automáticamente como compra o venta.",
        "",
        "--- ESTIMACIONES Y HORIZONTES ---",
    ])

    if estimaciones:
        for est in estimaciones:
            h = est.get("horizonte", "?")
            estado = est.get("estado", "INDETERMINADA")
            razon = est.get("razon", "")
            lineas_texto.append(f"- Horizonte {h}: Estado [{estado}]. {razon}")
    else:
        lineas_texto.append("Sin estimaciones registradas.")

    lineas_texto.extend([
        "",
        "--------------------------------------------------",
        DISCLAIMER_TEXTO,
    ])

    cuerpo_texto = "\n".join(lineas_texto)

    # HTML
    filas_est_html = ""
    for est in estimaciones:
        h = est.get("horizonte", "?")
        estado = est.get("estado", "INDETERMINADA")
        razon = est.get("razon", "")
        filas_est_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{h}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><span style="background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: 600; color: #475569;">{estado}</span></td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-size: 13px; color: #475569;">{razon}</td>
        </tr>
        """

    valor_usd_html = ""
    if valor_usd is not None and precio_usd is not None:
        valor_usd_html = f"<div style='font-size: 14px; color: #64748b;'>≈ ${valor_usd:,.2f} USD <span style='font-size: 12px;'>(Ref: ${precio_usd:,.2f})</span></div>"

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="{ESTILO_BASE_HTML}">
        <div style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden;">
            {_encabezado_html("Alerta de Movimiento On-Chain", categoria)}
            <div style="padding: 24px;">
                <div style="text-align: center; margin-bottom: 20px; padding: 16px; background-color: #f8fafc; border-radius: 6px;">
                    <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b;">Monto Relevante Detectado</div>
                    <div style="font-size: 28px; font-weight: 800; color: #0284c7; margin: 4px 0;">{monto_btc:,.4f} BTC</div>
                    {valor_usd_html}
                </div>

                <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 18px;">
                    <tr>
                        <td style="padding: 6px 0; color: #64748b; width: 35%;">Categoría:</td>
                        <td style="padding: 6px 0; font-weight: 600;">{categoria}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;">Origen:</td>
                        <td style="padding: 6px 0; font-weight: 600;">{entidad_origen}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;">Destino:</td>
                        <td style="padding: 6px 0; font-weight: 600;">{entidad_destino}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;">Confianza Atribución:</td>
                        <td style="padding: 6px 0; font-weight: 600;">{confianza * 100:.1f}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;">Transacción:</td>
                        <td style="padding: 6px 0;"><a href="{enlace_tx}" style="color: #0284c7; text-decoration: none; word-break: break-all;">Ver en explorador ({txid[:12]}...)</a></td>
                    </tr>
                </table>

                <div style="background-color: #f8fafc; border-left: 3px solid #0284c7; padding: 12px; margin-bottom: 16px; font-size: 13px;">
                    <strong>Evidencia observada:</strong><br>{evidencia}
                </div>

                <div style="background-color: #fffbeb; border-left: 3px solid #f59e0b; padding: 12px; margin-bottom: 16px; font-size: 13px; color: #92400e;">
                    <strong>Limitaciones y no-inferencia:</strong><br>{limitaciones}<br>
                    <em>Nota: No debe interpretarse automáticamente como una compra o venta.</em>
                </div>

                <h3 style="font-size: 15px; margin: 18px 0 8px 0; color: #0f172a;">Estimaciones de Impacto</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left;">
                            <th style="padding: 8px;">Horizonte</th>
                            <th style="padding: 8px;">Estado</th>
                            <th style="padding: 8px;">Detalle</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_est_html if filas_est_html else "<tr><td colspan='3' style='padding: 8px; color: #64748b;'>Sin estimaciones registradas</td></tr>"}
                    </tbody>
                </table>

                {_pie_disclaimer_html()}
            </div>
        </div>
    </body>
    </html>
    """

    return asunto, cuerpo_texto, cuerpo_html


def generar_plantilla_reporte_diario(datos_reporte: dict[str, Any]) -> tuple[str, str, str]:
    """Genera (asunto, texto_plano, html) para el informe diario consolidado."""
    fecha = datos_reporte.get("fecha", "")
    total_eventos = datos_reporte.get("total_eventos", 0)
    volumen_total_btc = datos_reporte.get("volumen_total_btc", 0.0)
    entidades_activas = datos_reporte.get("entidades_activas", [])
    evaluaciones = datos_reporte.get("evaluaciones_recientes", [])

    asunto = f"[BTC Whale Intelligence] Informe Diario Consolidado - {fecha}"

    # Texto
    lineas_texto = [
        f"=== BTC WHALE INTELLIGENCE: INFORME DIARIO ({fecha}) ===",
        f"Eventos Relevantes Detectados: {total_eventos}",
        f"Volumen Total Analizado: {volumen_total_btc:,.2f} BTC",
        "",
        "--- ENTIDADES ACTIVAS Y FLUJO NETO ESTIMADO ---",
    ]
    if entidades_activas:
        for ent in entidades_activas:
            nombre = ent.get("nombre", "Desconocida")
            flujo = ent.get("flujo_neto_btc", 0.0)
            movs = ent.get("movimientos", 0)
            signo = "+" if flujo > 0 else ""
            lineas_texto.append(f"- {nombre}: {signo}{flujo:,.2f} BTC ({movs} movs)")
    else:
        lineas_texto.append("Sin actividad de entidades registradas en el período.")

    lineas_texto.extend([
        "",
        "--- EVALUACIONES HISTÓRICAS RECIENTES VS BASELINES ---",
    ])
    if evaluaciones:
        for ev in evaluaciones:
            h = ev.get("horizonte", "?")
            ret_real = ev.get("retorno_real_pct", 0.0)
            bh = ev.get("retorno_buy_hold_pct", 0.0)
            cat = ev.get("resultado_categoria", "NEUTRAL")
            lineas_texto.append(f"- Horiz {h}: Real {ret_real:+.2f}% ({cat}) | Buy&Hold: {bh:+.2f}%")
    else:
        lineas_texto.append("Sin predicciones vencidas evaluadas en este período.")

    lineas_texto.extend([
        "",
        "--------------------------------------------------",
        DISCLAIMER_TEXTO,
    ])
    cuerpo_texto = "\n".join(lineas_texto)

    # HTML
    filas_entidades_html = ""
    for ent in entidades_activas:
        nombre = ent.get("nombre", "Desconocida")
        flujo = ent.get("flujo_neto_btc", 0.0)
        movs = ent.get("movimientos", 0)
        color_flujo = "#16a34a" if flujo > 0 else ("#dc2626" if flujo < 0 else "#64748b")
        signo = "+" if flujo > 0 else ""
        filas_entidades_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{nombre}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: center;">{movs}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 700; color: {color_flujo};">{signo}{flujo:,.2f} BTC</td>
        </tr>
        """

    filas_eval_html = ""
    for ev in evaluaciones:
        h = ev.get("horizonte", "?")
        ret_real = ev.get("retorno_real_pct", 0.0)
        bh = ev.get("retorno_buy_hold_pct", 0.0)
        cat = ev.get("resultado_categoria", "NEUTRAL")
        filas_eval_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{h}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{cat}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">{ret_real:+.2f}%</td>
            <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #64748b;">{bh:+.2f}%</td>
        </tr>
        """

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="{ESTILO_BASE_HTML}">
        <div style="max-width: 620px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden;">
            {_encabezado_html("Informe Diario Consolidado", fecha)}
            <div style="padding: 24px;">
                <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                    <div style="flex: 1; padding: 14px; background-color: #f8fafc; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Eventos Detectados</div>
                        <div style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px;">{total_eventos}</div>
                    </div>
                    <div style="flex: 1; padding: 14px; background-color: #f8fafc; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">Volumen Total</div>
                        <div style="font-size: 22px; font-weight: 800; color: #0284c7; margin-top: 4px;">{volumen_total_btc:,.2f} BTC</div>
                    </div>
                </div>

                <h3 style="font-size: 15px; margin: 18px 0 8px 0; color: #0f172a;">Actividad por Entidad</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 18px;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left;">
                            <th style="padding: 8px;">Entidad</th>
                            <th style="padding: 8px; text-align: center;">Movs</th>
                            <th style="padding: 8px; text-align: right;">Flujo Neto</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_entidades_html if filas_entidades_html else "<tr><td colspan='3' style='padding: 8px; color: #64748b;'>Sin actividad registrada</td></tr>"}
                    </tbody>
                </table>

                <h3 style="font-size: 15px; margin: 18px 0 8px 0; color: #0f172a;">Evaluaciones Vencidas vs Baselines</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px;">
                    <thead>
                        <tr style="background-color: #f1f5f9; text-align: left;">
                            <th style="padding: 8px;">Horizonte</th>
                            <th style="padding: 8px;">Categoría</th>
                            <th style="padding: 8px; text-align: right;">Retorno Real</th>
                            <th style="padding: 8px; text-align: right;">Buy & Hold</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_eval_html if filas_eval_html else "<tr><td colspan='4' style='padding: 8px; color: #64748b;'>Sin evaluaciones en este ciclo</td></tr>"}
                    </tbody>
                </table>

                {_pie_disclaimer_html()}
            </div>
        </div>
    </body>
    </html>
    """

    return asunto, cuerpo_texto, cuerpo_html


def generar_plantilla_error_critico(
    componente: str,
    tipo_error: str,
    mensaje: str,
    contexto: Optional[str] = None,
) -> tuple[str, str, str]:
    """Genera (asunto, texto_plano, html) para alertas operativas."""
    asunto = f"[ERROR CRÍTICO] Falla en componente {componente}: {tipo_error}"

    lineas_texto = [
        f"=== BTC WHALE INTELLIGENCE: ERROR CRÍTICO ===",
        f"Componente: {componente}",
        f"Tipo de Error: {tipo_error}",
        f"Detalle: {mensaje}",
    ]
    if contexto:
        lineas_texto.append(f"Contexto Operativo: {contexto}")
    lineas_texto.append("\nRevise los registros del sistema (logs) y el estado del servicio.")
    cuerpo_texto = "\n".join(lineas_texto)

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="{ESTILO_BASE_HTML}">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border-top: 4px solid #dc2626; padding: 20px;">
            <h2 style="color: #dc2626; margin-top: 0;">⚠️ Falla Operativa Crítica</h2>
            <p>Se ha producido un error que requiere atención:</p>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <tr><td style="padding: 6px 0; color: #64748b; width: 30%;">Componente:</td><td style="font-weight: 600;">{componente}</td></tr>
                <tr><td style="padding: 6px 0; color: #64748b;">Tipo de Error:</td><td style="font-weight: 600; color: #b91c1c;">{tipo_error}</td></tr>
                <tr><td style="padding: 6px 0; color: #64748b;">Detalle:</td><td>{mensaje}</td></tr>
                {f"<tr><td style='padding: 6px 0; color: #64748b;'>Contexto:</td><td>{contexto}</td></tr>" if contexto else ""}
            </table>
        </div>
    </body>
    </html>
    """

    return asunto, cuerpo_texto, cuerpo_html
