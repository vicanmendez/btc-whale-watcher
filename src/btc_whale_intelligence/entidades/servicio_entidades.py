"""Servicio de gestión de entidades y resolución de direcciones (RF-01, RF-02, RF-04).

Cumple los principios III y IV de la Constitución:
- Atribución documentada con grado de certeza y fuente.
- No asume que una entidad controla una dirección sin evidencia documentada.
- Agrega saldos de direcciones atribuidas a una entidad sin sumar dos veces una misma dirección.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..base_datos.modelos import AtribucionDireccionORM, DireccionORM, EntidadORM
from ..tiempo import ahora_utc


def detectar_formato_direccion(direccion_btc: str) -> str:
    """Infiere el formato de la dirección de Bitcoin a partir de su prefijo."""
    d = direccion_btc.strip()
    if d.startswith("1"):
        return "P2PKH"
    if d.startswith("3"):
        return "P2SH"
    if d.startswith("bc1q") or d.startswith("tb1q"):
        return "P2WPKH" if len(d) <= 44 else "P2WSH"
    if d.startswith("bc1p") or d.startswith("tb1p"):
        return "P2TR"
    return "DESCONOCIDO"


class ServicioEntidades:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def registrar_entidad(
        self,
        nombre: str,
        categoria: str,
        nivel_confianza: float,
        fuentes_identificacion: str,
        umbral_personalizado_btc: Optional[float] = None,
        notas: Optional[str] = None,
    ) -> EntidadORM:
        """Registra o actualiza una entidad en el catálogo."""
        consulta = select(EntidadORM).where(EntidadORM.nombre == nombre.strip())
        entidad = self.sesion.scalars(consulta).first()
        if entidad is None:
            entidad = EntidadORM(
                nombre=nombre.strip(),
                categoria=categoria.strip(),
                nivel_confianza=float(nivel_confianza),
                fuentes_identificacion=fuentes_identificacion.strip(),
                umbral_personalizado_btc=umbral_personalizado_btc,
                notas=notas,
                activo=True,
            )
            self.sesion.add(entidad)
        else:
            entidad.categoria = categoria.strip()
            entidad.nivel_confianza = float(nivel_confianza)
            entidad.fuentes_identificacion = fuentes_identificacion.strip()
            if umbral_personalizado_btc is not None:
                entidad.umbral_personalizado_btc = umbral_personalizado_btc
            if notas is not None:
                entidad.notas = notas
            entidad.actualizado_en = ahora_utc()
        self.sesion.flush()
        return entidad

    def registrar_o_obtener_direccion(
        self, direccion_btc: str, formato: Optional[str] = None
    ) -> DireccionORM:
        """Obtiene o crea una dirección en la base de datos."""
        dir_limpia = direccion_btc.strip()
        consulta = select(DireccionORM).where(DireccionORM.direccion_btc == dir_limpia)
        direccion = self.sesion.scalars(consulta).first()
        if direccion is None:
            fmt = formato or detectar_formato_direccion(dir_limpia)
            direccion = DireccionORM(
                direccion_btc=dir_limpia,
                formato=fmt,
                saldo_actual_satoshis=None,
                conteo_transacciones=None,
            )
            self.sesion.add(direccion)
            self.sesion.flush()
        return direccion

    def atribuir_direccion(
        self,
        direccion_btc: str,
        nombre_entidad: str,
        grado_certeza: float,
        fuente_atribucion: str,
        fecha_verificacion: date,
        formato: Optional[str] = None,
    ) -> AtribucionDireccionORM:
        """Asocia una dirección a una entidad con respaldo documental."""
        if not fuente_atribucion or not fuente_atribucion.strip():
            raise ValueError("La fuente de atribución es obligatoria y no puede estar vacía")

        direccion = self.registrar_o_obtener_direccion(direccion_btc, formato)
        consulta_ent = select(EntidadORM).where(EntidadORM.nombre == nombre_entidad.strip())
        entidad = self.sesion.scalars(consulta_ent).first()
        if entidad is None:
            raise ValueError(f"Entidad no encontrada: '{nombre_entidad}'")

        consulta_atrib = select(AtribucionDireccionORM).where(
            AtribucionDireccionORM.direccion_id == direccion.id,
            AtribucionDireccionORM.entidad_id == entidad.id,
        )
        atribucion = self.sesion.scalars(consulta_atrib).first()
        if atribucion is None:
            atribucion = AtribucionDireccionORM(
                direccion_id=direccion.id,
                entidad_id=entidad.id,
                grado_certeza=float(grado_certeza),
                fuente_atribucion=fuente_atribucion.strip(),
                fecha_verificacion=fecha_verificacion,
                activo=True,
            )
            self.sesion.add(atribucion)
        else:
            atribucion.grado_certeza = float(grado_certeza)
            atribucion.fuente_atribucion = fuente_atribucion.strip()
            atribucion.fecha_verificacion = fecha_verificacion
            atribucion.activo = True

        self.sesion.flush()
        return atribucion

    def resolver_entidad_por_direccion(
        self, direccion_btc: str, certeza_minima: float = 0.7
    ) -> Optional[tuple[EntidadORM, float, str]]:
        """Busca si una dirección está atribuida a una entidad activa con suficiente certeza.

        Retorna (Entidad, grado_certeza, fuente_atribucion) o None.
        """
        consulta = (
            select(EntidadORM, AtribucionDireccionORM.grado_certeza, AtribucionDireccionORM.fuente_atribucion)
            .join(AtribucionDireccionORM, AtribucionDireccionORM.entidad_id == EntidadORM.id)
            .join(DireccionORM, DireccionORM.id == AtribucionDireccionORM.direccion_id)
            .where(
                DireccionORM.direccion_btc == direccion_btc.strip(),
                AtribucionDireccionORM.activo.is_(True),
                EntidadORM.activo.is_(True),
                AtribucionDireccionORM.grado_certeza >= certeza_minima,
            )
            .order_by(AtribucionDireccionORM.grado_certeza.desc())
        )
        resultado = self.sesion.execute(consulta).first()
        if resultado is None:
            return None
        return resultado[0], float(resultado[1]), str(resultado[2])

    def calcular_saldo_agregado_entidad(
        self, entidad_id: int, certeza_minima: float = 0.7
    ) -> tuple[int, int]:
        """Calcula el saldo total en satoshis y el conteo de direcciones de una entidad.

        Garantiza que no se suma dos veces una misma dirección (RF-04).
        Retorna (total_satoshis, cantidad_direcciones).
        """
        consulta = (
            select(DireccionORM.saldo_actual_satoshis)
            .distinct()
            .join(AtribucionDireccionORM, AtribucionDireccionORM.direccion_id == DireccionORM.id)
            .where(
                AtribucionDireccionORM.entidad_id == entidad_id,
                AtribucionDireccionORM.activo.is_(True),
                AtribucionDireccionORM.grado_certeza >= certeza_minima,
            )
        )
        saldos = self.sesion.scalars(consulta).all()
        total_satoshis = sum(s for s in saldos if s is not None)
        return total_satoshis, len(saldos)

    def listar_entidades_activas(self) -> Sequence[EntidadORM]:
        return self.sesion.scalars(
            select(EntidadORM).where(EntidadORM.activo.is_(True)).order_by(EntidadORM.nombre)
        ).all()

    def obtener_o_crear_entidad_ballena(self, direccion_btc: str) -> EntidadORM:
        """Obtiene o registra una entidad de tipo Gran_Tenedor para una billetera ballena on-chain."""
        res = self.resolver_entidad_por_direccion(direccion_btc, 0.5)
        if res is not None:
            return res[0]

        dir_limpia = direccion_btc.strip()
        dir_corta = f"{dir_limpia[:6]}...{dir_limpia[-4:]}"
        nombre = f"Ballena ({dir_corta})"
        consulta = select(EntidadORM).where(EntidadORM.nombre == nombre)
        ent = self.sesion.scalars(consulta).first()
        if ent is None:
            ent = self.registrar_entidad(
                nombre=nombre,
                categoria="Gran_Tenedor",
                nivel_confianza=0.85,
                fuentes_identificacion=f"Detección de billetera ballena en blockchain de Bitcoin. Rastreable en BTCScan y Mempool (dirección {dir_limpia}).",
                umbral_personalizado_btc=500.0,
                notas=f"Dirección on-chain: {dir_limpia}",
            )
            self.atribuir_direccion(
                direccion_btc=dir_limpia,
                nombre_entidad=nombre,
                grado_certeza=0.90,
                fuente_atribucion="Observación directa on-chain en bloque y verificación en BTCScan / Mempool.space",
                fecha_verificacion=date.today(),
            )
        return ent
