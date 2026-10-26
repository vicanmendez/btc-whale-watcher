from datetime import date
import pytest

from btc_whale_intelligence.entidades.servicio_entidades import (
    ServicioEntidades,
    detectar_formato_direccion,
)


def test_detectar_formato_direccion():
    assert detectar_formato_direccion("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "P2PKH"
    assert detectar_formato_direccion("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == "P2SH"
    assert detectar_formato_direccion("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4") == "P2WPKH"
    assert detectar_formato_direccion("bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0") == "P2TR"


def test_registrar_y_resolver_entidad(sesion):
    servicio = ServicioEntidades(sesion)
    entidad = servicio.registrar_entidad(
        nombre="Binance",
        categoria="Exchange",
        nivel_confianza=0.99,
        fuentes_identificacion="Proof of Reserves",
        umbral_personalizado_btc=500,
    )
    assert entidad.id is not None

    dir_btc = "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
    servicio.atribuir_direccion(
        direccion_btc=dir_btc,
        nombre_entidad="Binance",
        grado_certeza=0.95,
        fuente_atribucion="PoR Oficial",
        fecha_verificacion=date(2026, 1, 1),
    )

    res = servicio.resolver_entidad_por_direccion(dir_btc, certeza_minima=0.7)
    assert res is not None
    ent, certeza, fuente = res
    assert ent.nombre == "Binance"
    assert certeza == 0.95
    assert fuente == "PoR Oficial"


def test_no_asume_entidad_si_certeza_insuficiente(sesion):
    servicio = ServicioEntidades(sesion)
    servicio.registrar_entidad("ExchangeDudoso", "Exchange", 0.5, "Foro internet")
    dir_btc = "1Dudoso123456789"
    servicio.atribuir_direccion(
        direccion_btc=dir_btc,
        nombre_entidad="ExchangeDudoso",
        grado_certeza=0.4,
        fuente_atribucion="Post de Reddit no verificado",
        fecha_verificacion=date(2026, 1, 1),
    )

    # Con umbral de certeza 0.7 (por defecto) no debe resolver la entidad (Principio III)
    assert servicio.resolver_entidad_por_direccion(dir_btc, certeza_minima=0.7) is None


def test_calcular_saldo_agregado_sin_duplicar_direcciones(sesion):
    servicio = ServicioEntidades(sesion)
    entidad = servicio.registrar_entidad("MicroStrategy", "Empresa", 0.98, "SEC 8-K")

    dir1 = servicio.registrar_o_obtener_direccion("1DirUno")
    dir1.saldo_actual_satoshis = 100_000_000  # 1 BTC
    dir2 = servicio.registrar_o_obtener_direccion("1DirDos")
    dir2.saldo_actual_satoshis = 200_000_000  # 2 BTC

    servicio.atribuir_direccion("1DirUno", "MicroStrategy", 0.95, "SEC", date(2026, 1, 1))
    servicio.atribuir_direccion("1DirDos", "MicroStrategy", 0.95, "SEC", date(2026, 1, 1))

    total, cantidad = servicio.calcular_saldo_agregado_entidad(entidad.id)
    assert total == 300_000_000
    assert cantidad == 2
