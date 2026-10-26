import json
from btc_whale_intelligence.entidades.importador_semillas import (
    importar_desde_csv,
    importar_desde_json,
)
from btc_whale_intelligence.entidades.servicio_entidades import ServicioEntidades


def test_importar_desde_csv(tmp_path, sesion):
    archivo_csv = tmp_path / "semilla.csv"
    archivo_csv.write_text(
        "nombre_entidad,categoria,nivel_confianza,fuentes_identificacion,direccion_btc,grado_certeza,fuente_atribucion,fecha_verificacion\n"
        "Kraken,Exchange,0.98,Reporte de auditoría,3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5,0.95,Auditoría PoR,2026-01-01\n"
        "Tesla,Empresa,0.90,SEC 10-K,1TeslaAddressDummy12345,0.85,SEC Filing,2026-01-01\n",
        encoding="utf-8",
    )

    resultado = importar_desde_csv(sesion, archivo_csv)
    assert resultado.entidades_procesadas == 2
    assert resultado.direcciones_procesadas == 2
    assert resultado.atribuciones_creadas == 2
    assert resultado.filas_con_error == 0

    servicio = ServicioEntidades(sesion)
    entidades = servicio.listar_entidades_activas()
    assert len(entidades) == 2
    assert {e.nombre for e in entidades} == {"Kraken", "Tesla"}


def test_importar_desde_json(tmp_path, sesion):
    archivo_json = tmp_path / "semilla.json"
    contenido = [
        {
            "nombre": "BitGo",
            "categoria": "Custodio",
            "nivel_confianza": 0.95,
            "fuentes_identificacion": "Reportes institucionales",
            "direcciones": [
                {
                    "direccion_btc": "bc1qbitgo123456789",
                    "grado_certeza": 0.92,
                    "fuente_atribucion": "Custody proof",
                    "fecha_verificacion": "2026-02-01",
                }
            ],
        }
    ]
    archivo_json.write_text(json.dumps(contenido), encoding="utf-8")

    resultado = importar_desde_json(sesion, archivo_json)
    assert resultado.entidades_procesadas == 1
    assert resultado.direcciones_procesadas == 1
    assert resultado.atribuciones_creadas == 1
    assert resultado.filas_con_error == 0
