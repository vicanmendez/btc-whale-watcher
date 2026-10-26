"""Despachador de alertas y reportes por correo electrónico SMTP con idempotencia."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import logging
import smtplib
from typing import Optional

from sqlalchemy.orm import Session

from btc_whale_intelligence.base_datos.modelos import AlertaDespachadaORM
from btc_whale_intelligence.configuracion import Configuracion
from btc_whale_intelligence.tiempo import ahora_utc

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertaMensaje:
    evento_id: Optional[int]
    asunto: str
    cuerpo_texto: str
    cuerpo_html: str
    destinatario: str
    tipo_alerta: str  # "MOVIMIENTO_RELEVANTE", "INFORME_DIARIO", "ERROR_CRITICO"


@dataclass(frozen=True)
class ResultadoEnvio:
    exito: bool
    identificador_envio: Optional[str] = None
    error_detalle: Optional[str] = None
    ya_enviado: bool = False


class DespachadorSMTP:
    """Gestiona el despacho seguro de correos SMTP garantizando no duplicación por idempotencia."""

    def __init__(self, configuracion: Configuracion, sesion: Session) -> None:
        self._config = configuracion
        self._sesion = sesion

    def _calcular_claves_idempotencia(self, mensaje: AlertaMensaje) -> tuple[str, str]:
        if mensaje.tipo_alerta == "MOVIMIENTO_RELEVANTE" and mensaje.evento_id is not None:
            clave = f"movimiento:{mensaje.evento_id}:{mensaje.destinatario}"
        elif mensaje.tipo_alerta == "INFORME_DIARIO":
            clave = f"informe_diario:{mensaje.asunto}:{mensaje.destinatario}"
        else:
            resumen_asunto = hashlib.sha256(mensaje.asunto.encode("utf-8")).hexdigest()[:16]
            clave = f"{mensaje.tipo_alerta}:{resumen_asunto}:{mensaje.destinatario}"

        hash_idemp = hashlib.sha256(clave.encode("utf-8")).hexdigest()
        return clave, hash_idemp

    def enviar_alerta(self, mensaje: AlertaMensaje) -> ResultadoEnvio:
        """Despacha un correo electrónico validando idempotencia y registrando el resultado."""
        clave_idemp, hash_idemp = self._calcular_claves_idempotencia(mensaje)

        # Verificar si ya fue despachado previamente
        registro = self._sesion.query(AlertaDespachadaORM).filter_by(hash_idempotencia=hash_idemp).first()
        if registro is not None and registro.estado == "ENVIADO":
            _logger.info(
                "Alerta omitida por idempotencia: ya enviada previamente",
                extra={"hash_idempotencia": hash_idemp, "destinatario": mensaje.destinatario},
            )
            return ResultadoEnvio(
                exito=True,
                identificador_envio=hash_idemp,
                ya_enviado=True,
            )

        if registro is None:
            registro = AlertaDespachadaORM(
                evento_id=mensaje.evento_id,
                tipo_alerta=mensaje.tipo_alerta,
                clave_idempotencia=clave_idemp,
                hash_idempotencia=hash_idemp,
                canal="EMAIL_SMTP",
                destinatario=mensaje.destinatario,
                asunto=mensaje.asunto,
                cuerpo_texto=mensaje.cuerpo_texto,
                cuerpo_html=mensaje.cuerpo_html,
                estado="PENDIENTE",
                intentos=0,
            )
            self._sesion.add(registro)
            self._sesion.commit()

        # Construir mensaje MIME multipart/alternative
        msg = MIMEMultipart("alternative")
        msg["Subject"] = mensaje.asunto
        msg["From"] = self._config.smtp_remitente or "whalewatcher@localhost"
        msg["To"] = mensaje.destinatario

        parte_texto = MIMEText(mensaje.cuerpo_texto, "plain", "utf-8")
        parte_html = MIMEText(mensaje.cuerpo_html, "html", "utf-8")
        msg.attach(parte_texto)
        msg.attach(parte_html)

        try:
            registro.intentos += 1
            self._enviar_correo_servidor(msg, mensaje.destinatario)
            registro.estado = "ENVIADO"
            registro.despachado_en = ahora_utc()
            registro.ultimo_error = None
            self._sesion.commit()

            _logger.info(
                "Alerta SMTP enviada exitosamente",
                extra={"destinatario": mensaje.destinatario, "tipo": mensaje.tipo_alerta},
            )
            return ResultadoEnvio(exito=True, identificador_envio=hash_idemp)

        except Exception as error:
            registro.estado = "FALLIDO"
            registro.ultimo_error = str(error)
            self._sesion.commit()

            _logger.error(
                "Error al despachar alerta SMTP",
                extra={"destinatario": mensaje.destinatario, "error": str(error)},
            )
            return ResultadoEnvio(exito=False, error_detalle=str(error))

    def _enviar_correo_servidor(self, mensaje_mime: MIMEMultipart, destinatario: str) -> None:
        """Conexión y envío al servidor SMTP según configuración."""
        host = self._config.smtp_host
        puerto = self._config.smtp_puerto
        timeout = self._config.smtp_timeout_seg

        if self._config.smtp_ssl:
            servidor_smtp = smtplib.SMTP_SSL(host, puerto, timeout=timeout)
        else:
            servidor_smtp = smtplib.SMTP(host, puerto, timeout=timeout)

        with servidor_smtp as servidor:
            servidor.ehlo()
            if self._config.smtp_starttls and not self._config.smtp_ssl:
                servidor.starttls()
                servidor.ehlo()

            if self._config.smtp_usuario and self._config.smtp_contrasena:
                servidor.login(self._config.smtp_usuario, self._config.smtp_contrasena)

            servidor.send_message(mensaje_mime)

    def despachar_a_destinatarios(
        self,
        asunto: str,
        cuerpo_texto: str,
        cuerpo_html: str,
        tipo_alerta: str,
        evento_id: Optional[int] = None,
    ) -> list[ResultadoEnvio]:
        """Envía el mensaje a todos los destinatarios configurados."""
        resultados: list[ResultadoEnvio] = []
        destinatarios = self._config.destinatarios_alerta
        if not destinatarios:
            _logger.warning("No hay destinatarios de alerta configurados en DESTINATARIOS_ALERTA")
            return resultados

        for dest in destinatarios:
            msg = AlertaMensaje(
                evento_id=evento_id,
                asunto=asunto,
                cuerpo_texto=cuerpo_texto,
                cuerpo_html=cuerpo_html,
                destinatario=dest,
                tipo_alerta=tipo_alerta,
            )
            res = self.enviar_alerta(msg)
            resultados.append(res)

        return resultados
