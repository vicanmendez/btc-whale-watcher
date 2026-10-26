"""Cargador e importador masivo de entidades y direcciones desde CSV y JSON (RF-02)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session

from .servicio_entidades import ServicioEntidades


@dataclass(frozen=True)
class ResultadoImportacion:
    entidades_procesadas: int
    direcciones_procesadas: int
    atribuciones_creadas: int
    filas_con_error: int
    errores: tuple[str, ...]


def _parsear_fecha(valor: str) -> date:
    val = valor.strip()
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except ValueError:
        return date.fromisoformat(val)


def importar_desde_csv(sesion: Session, ruta_archivo: str | Path) -> ResultadoImportacion:
    """Importa entidades y direcciones desde un archivo CSV delimitado por comas."""
    ruta = Path(ruta_archivo)
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    servicio = ServicioEntidades(sesion)
    entidades_vistas = set()
    direcciones_vistas = set()
    atribuciones_creadas = 0
    errores: list[str] = []

    with open(ruta, "r", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        for num_fila, fila in enumerate(lector, start=2):
            try:
                nombre = (fila.get("nombre_entidad") or fila.get("entidad") or "").strip()
                categoria = (fila.get("categoria") or "").strip()
                nivel_confianza_str = fila.get("nivel_confianza") or "1.0"
                fuentes_identificacion = (fila.get("fuentes_identificacion") or "Divulgación pública").strip()
                direccion_btc = (fila.get("direccion_btc") or fila.get("direccion") or "").strip()
                grado_certeza_str = fila.get("grado_certeza") or "1.0"
                fuente_atribucion = (fila.get("fuente_atribucion") or fuentes_identificacion).strip()
                fecha_verif_str = (fila.get("fecha_verificacion") or "2026-01-01").strip()

                if not nombre or not categoria:
                    errores.append(f"Fila {num_fila}: nombre de entidad o categoría vacía")
                    continue

                umbral_str = fila.get("umbral_personalizado_btc")
                umbral_btc = float(umbral_str) if umbral_str and umbral_str.strip() else None

                entidad = servicio.registrar_entidad(
                    nombre=nombre,
                    categoria=categoria,
                    nivel_confianza=float(nivel_confianza_str),
                    fuentes_identificacion=fuentes_identificacion,
                    umbral_personalizado_btc=umbral_btc,
                    notas=fila.get("notas"),
                )
                entidades_vistas.add(entidad.id)

                if direccion_btc:
                    fecha_verif = _parsear_fecha(fecha_verif_str)
                    formato = fila.get("formato_direccion")
                    atrib = servicio.atribuir_direccion(
                        direccion_btc=direccion_btc,
                        nombre_entidad=nombre,
                        grado_certeza=float(grado_certeza_str),
                        fuente_atribucion=fuente_atribucion,
                        fecha_verificacion=fecha_verif,
                        formato=formato.strip() if formato else None,
                    )
                    direcciones_vistas.add(direccion_btc)
                    atribuciones_creadas += 1

            except Exception as exc:
                errores.append(f"Fila {num_fila}: {exc}")

    return ResultadoImportacion(
        entidades_procesadas=len(entidades_vistas),
        direcciones_procesadas=len(direcciones_vistas),
        atribuciones_creadas=atribuciones_creadas,
        filas_con_error=len(errores),
        errores=tuple(errores),
    )


def importar_desde_json(sesion: Session, ruta_archivo: str | Path) -> ResultadoImportacion:
    """Importa entidades y direcciones desde un archivo JSON estructurado."""
    ruta = Path(ruta_archivo)
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)

    if not isinstance(datos, list):
        datos = datos.get("entidades", [])

    servicio = ServicioEntidades(sesion)
    entidades_vistas = set()
    direcciones_vistas = set()
    atribuciones_creadas = 0
    errores: list[str] = []

    for idx, item in enumerate(datos, start=1):
        try:
            nombre = item.get("nombre") or item.get("nombre_entidad")
            categoria = item.get("categoria")
            confianza = float(item.get("nivel_confianza", 1.0))
            fuentes = item.get("fuentes_identificacion", "Archivo semilla JSON")
            umbral = item.get("umbral_personalizado_btc")

            entidad = servicio.registrar_entidad(
                nombre=nombre,
                categoria=categoria,
                nivel_confianza=confianza,
                fuentes_identificacion=fuentes,
                umbral_personalizado_btc=float(umbral) if umbral is not None else None,
                notas=item.get("notas"),
            )
            entidades_vistas.add(entidad.id)

            if item.get("direccion_btc"):
                dir_btc = item["direccion_btc"]
                certeza = float(item.get("grado_certeza", item.get("nivel_confianza", 0.95)))
                fuente_atr = item.get("fuente_atribucion") or item.get("fuente") or fuentes
                f_verif = _parsear_fecha(str(item.get("fecha_verificacion", "2026-10-25")))
                servicio.atribuir_direccion(
                    direccion_btc=dir_btc,
                    nombre_entidad=nombre,
                    grado_certeza=certeza,
                    fuente_atribucion=fuente_atr,
                    fecha_verificacion=f_verif,
                )
                direcciones_vistas.add(dir_btc)
                atribuciones_creadas += 1

            for d in item.get("direcciones", []):
                if isinstance(d, str):
                    dir_btc = d
                    certeza = 1.0
                    fuente_atr = fuentes
                    f_verif = date(2026, 1, 1)
                else:
                    dir_btc = d["direccion_btc"]
                    certeza = float(d.get("grado_certeza", 1.0))
                    fuente_atr = d.get("fuente_atribucion", fuentes)
                    f_verif = _parsear_fecha(d.get("fecha_verificacion", "2026-01-01"))

                servicio.atribuir_direccion(
                    direccion_btc=dir_btc,
                    nombre_entidad=nombre,
                    grado_certeza=certeza,
                    fuente_atribucion=fuente_atr,
                    fecha_verificacion=f_verif,
                )
                direcciones_vistas.add(dir_btc)
                atribuciones_creadas += 1

        except Exception as exc:
            errores.append(f"Elemento {idx}: {exc}")

    return ResultadoImportacion(
        entidades_procesadas=len(entidades_vistas),
        direcciones_procesadas=len(direcciones_vistas),
        atribuciones_creadas=atribuciones_creadas,
        filas_con_error=len(errores),
        errores=tuple(errores),
    )
