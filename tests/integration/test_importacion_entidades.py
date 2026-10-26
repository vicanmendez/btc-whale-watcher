from pathlib import Path
from btc_whale_intelligence.entidades.importador_semillas import importar_desde_csv
from btc_whale_intelligence.entidades.servicio_entidades import ServicioEntidades


def test_importacion_completa_entidades_iniciales(sesion):
    ruta_semilla = Path("datos/semillas/entidades_iniciales.csv")
    assert ruta_semilla.exists()

    resultado = importar_desde_csv(sesion, ruta_semilla)
    assert resultado.filas_con_error == 0
    assert resultado.entidades_procesadas >= 7
    assert resultado.direcciones_procesadas >= 9
    assert resultado.atribuciones_creadas >= 9

    servicio = ServicioEntidades(sesion)
    res_binance = servicio.resolver_entidad_por_direccion(
        "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", certeza_minima=0.7
    )
    assert res_binance is not None
    entidad, certeza, fuente = res_binance
    assert entidad.nombre == "Binance"
    assert entidad.categoria == "Exchange"
    assert certeza >= 0.95
