from btc_whale_intelligence.configuracion import ErrorConfiguracion, cargar_configuracion
from btc_whale_intelligence.observabilidad import FiltroSecretos

import pytest


def test_valores_por_defecto_coinciden_con_especificacion():
    config = cargar_configuracion(entorno={})
    assert config.umbral_exchange_btc == 500
    assert config.umbral_institucional_btc == 250
    assert config.umbral_desconocido_btc == 1000
    assert config.modelo_predictivo == "indeterminado"
    assert config.umbral_neutral_pct("24H") == 1.0


def test_lee_variables_y_lista_destinatarios():
    config = cargar_configuracion(
        entorno={
            "UMBRAL_EXCHANGE_BTC": "750",
            "ALERT_EMAIL_TO": "a@x.com, b@y.com ,",
            "SMTP_STARTTLS": "no",
            "SMTP_SSL": "true",
            "ESPLORA_FALLBACK_URL": "",
        }
    )
    assert config.umbral_exchange_btc == 750
    assert config.destinatarios_alerta == ("a@x.com", "b@y.com")
    assert config.smtp_ssl and not config.smtp_starttls
    assert config.url_esplora_respaldo is None


@pytest.mark.parametrize(
    "entorno",
    [
        {"CERTEZA_MINIMA_ATRIBUCION": "1.5"},
        {"UMBRAL_EXCHANGE_BTC": "-1"},
        {"UMBRAL_EXCHANGE_BTC": "mucho"},
        {"SMTP_SSL": "true"},  # STARTTLS por defecto true -> excluyentes
        {"FRACCION_RESERVA_FINAL": "1"},
        {"ESCANEAR_BLOQUES_COMPLETOS": "quizas"},
    ],
)
def test_rechaza_configuracion_invalida(entorno):
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion(entorno=entorno)


def test_contrasena_no_aparece_en_repr():
    config = cargar_configuracion(entorno={"SMTP_PASSWORD": "super-secreta-123"})
    assert "super-secreta-123" not in repr(config)
    assert config.secretos() == ("super-secreta-123",)


def test_filtro_redacta_secretos_y_patrones():
    filtro = FiltroSecretos(["super-secreta-123"])
    texto = filtro.redactar(
        "fallo login super-secreta-123 en smtp://user:clave@host password=abc token: xyz"
    )
    assert "super-secreta-123" not in texto
    assert "clave" not in texto
    assert "abc" not in texto
    assert "xyz" not in texto
