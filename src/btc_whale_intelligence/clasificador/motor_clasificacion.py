"""Motor de clasificación formal de movimientos (RF-07, Principio IV).

Garantiza la regla inviolable:
BAJO NINGUNA CIRCUNSTANCIA SE DEBE CLASIFICAR UNA TRANSFERENCIA ON-CHAIN
COMO UNA "COMPRA" O "VENTA" AUTOMÁTICA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..onchain.detector_movimientos import CalificacionMovimiento, DetectorMovimientos
from ..onchain.parser_transaccion import TransaccionParsed


class MotorClasificacion:
    """Clasificador formal de eventos on-chain."""

    def __init__(self, detector: DetectorMovimientos) -> None:
        self.detector = detector

    def clasificar(self, transaccion: TransaccionParsed) -> CalificacionMovimiento:
        """Aplica la clasificación objetiva a la transacción."""
        calificacion = self.detector.evaluar_transaccion(transaccion)

        # Verificación de integridad constitucional (Principio IV)
        categoria_upper = calificacion.categoria.upper()
        if "COMPRA" in categoria_upper or "VENTA" in categoria_upper:
            raise ValueError(
                f"Violación Constitucional (Principio IV): Clasificación no permitida '{calificacion.categoria}'"
            )

        return calificacion
