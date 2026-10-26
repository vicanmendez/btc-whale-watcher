"""Pruebas unitarias para el despachador SMTP y control de idempotencia."""

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from btc_whale_intelligence.base_datos.modelos import Base, AlertaDespachadaORM
from btc_whale_intelligence.configuracion import Configuracion
from btc_whale_intelligence.notificaciones.despachador_smtp import DespachadorSMTP, AlertaMensaje


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
        smtp_usuario="usuario@ejemplo.com",
        smtp_contrasena="secreto123",
        smtp_remitente="alertas@whalewatcher.local",
        destinatarios_alerta=("analista@ejemplo.com",),
        smtp_starttls=True,
        smtp_ssl=False,
    )


def test_despacho_smtp_exitoso_y_registro_idempotente(sesion_bd, configuracion_smtp):
    despachador = DespachadorSMTP(configuracion_smtp, sesion_bd)

    mensaje = AlertaMensaje(
        evento_id=1,
        asunto="[ALERTA] Movimiento Relevante BTC",
        cuerpo_texto="Texto plano del mensaje",
        cuerpo_html="<html><body>HTML del mensaje</body></html>",
        destinatario="analista@ejemplo.com",
        tipo_alerta="MOVIMIENTO_RELEVANTE",
    )

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        resultado = despachador.enviar_alerta(mensaje)

        assert resultado.exito is True
        assert resultado.ya_enviado is False
        assert mock_servidor.send_message.called

    # Verificar registro en base de datos
    registro = sesion_bd.query(AlertaDespachadaORM).first()
    assert registro is not None
    assert registro.estado == "ENVIADO"
    assert registro.destinatario == "analista@ejemplo.com"
    assert registro.tipo_alerta == "MOVIMIENTO_RELEVANTE"
    assert registro.intentos == 1
    assert registro.hash_idempotencia is not None


def test_despacho_idempotente_no_reenvia(sesion_bd, configuracion_smtp):
    despachador = DespachadorSMTP(configuracion_smtp, sesion_bd)

    mensaje = AlertaMensaje(
        evento_id=2,
        asunto="[ALERTA] Movimiento Relevante BTC",
        cuerpo_texto="Texto",
        cuerpo_html="<html>Texto</html>",
        destinatario="analista@ejemplo.com",
        tipo_alerta="MOVIMIENTO_RELEVANTE",
    )

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_servidor = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_servidor

        # Primer envío
        res1 = despachador.enviar_alerta(mensaje)
        assert res1.exito is True
        assert res1.ya_enviado is False
        assert mock_servidor.send_message.call_count == 1

        # Segundo envío idéntico
        res2 = despachador.enviar_alerta(mensaje)
        assert res2.exito is True
        assert res2.ya_enviado is True
        # El servidor SMTP NO debe haber sido llamado de nuevo
        assert mock_servidor.send_message.call_count == 1


def test_despacho_smtp_falla_registra_error(sesion_bd, configuracion_smtp):
    despachador = DespachadorSMTP(configuracion_smtp, sesion_bd)

    mensaje = AlertaMensaje(
        evento_id=3,
        asunto="[ALERTA] Falla",
        cuerpo_texto="Texto",
        cuerpo_html="<html>Texto</html>",
        destinatario="analista@ejemplo.com",
        tipo_alerta="MOVIMIENTO_RELEVANTE",
    )

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.side_effect = ConnectionRefusedError("Conexión rechazada por el servidor")

        resultado = despachador.enviar_alerta(mensaje)

        assert resultado.exito is False
        assert "Conexión rechazada" in (resultado.error_detalle or "")

    registro = sesion_bd.query(AlertaDespachadaORM).filter_by(evento_id=3).first()
    assert registro is not None
    assert registro.estado == "FALLIDO"
    assert "Conexión rechazada" in registro.ultimo_error
