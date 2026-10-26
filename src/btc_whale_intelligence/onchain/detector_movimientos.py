"""Detector de movimientos relevantes según umbrales por categoría y entidades (RF-05, RF-07).

Aplica estrictamente los principios III y IV:
- Prohíbe interpretar cualquier transferencia como compra o venta.
- Clasifica según evidencia documentada: ENTRADA_EXCHANGE, SALIDA_EXCHANGE,
  TRANSFERENCIA_INTERNA, MOVIMIENTO_CORPORATIVO, DESCONOCIDA o INCIERTA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from ..base_datos.modelos import EventoAnalizadoORM, TransaccionOnChainORM
from ..configuracion import Configuracion
from ..entidades.servicio_entidades import ServicioEntidades
from .parser_transaccion import TransaccionParsed


@dataclass(frozen=True)
class CalificacionMovimiento:
    es_relevante: bool
    categoria: str
    monto_relevante_btc: float
    umbral_aplicado_btc: float
    entidad_origen_id: Optional[int]
    entidad_destino_id: Optional[int]
    nivel_confianza: float
    evidencia: str
    limitaciones: str


class DetectorMovimientos:
    def __init__(self, sesion: Session, config: Configuracion) -> None:
        self.sesion = sesion
        self.config = config
        self.servicio_entidades = ServicioEntidades(sesion)

    def evaluar_transaccion(self, tx: TransaccionParsed) -> CalificacionMovimiento:
        """Evalúa las entradas y salidas para detectar si supera umbrales y clasificar."""
        entidades_origen = set()
        entidades_destino = set()
        monto_origen_satoshis = {}
        monto_destino_satoshis = {}

        for entrada in tx.entradas:
            if entrada.direccion_btc:
                res = self.servicio_entidades.resolver_entidad_por_direccion(
                    entrada.direccion_btc, self.config.certeza_minima_atribucion
                )
                if res:
                    ent, certeza, _ = res
                    entidades_origen.add((ent.id, ent.nombre, ent.categoria, certeza, ent.umbral_personalizado_btc))
                    monto_origen_satoshis[ent.id] = monto_origen_satoshis.get(ent.id, 0) + entrada.monto_satoshis

        for salida in tx.salidas:
            if salida.direccion_btc:
                res = self.servicio_entidades.resolver_entidad_por_direccion(
                    salida.direccion_btc, self.config.certeza_minima_atribucion
                )
                if res:
                    ent, certeza, _ = res
                    entidades_destino.add((ent.id, ent.nombre, ent.categoria, certeza, ent.umbral_personalizado_btc))
                    monto_destino_satoshis[ent.id] = monto_destino_satoshis.get(ent.id, 0) + salida.monto_satoshis

        monto_total_btc = tx.total_salida_btc

        # 1. Caso: Transferencia interna (misma entidad en origen y destino con evidencia)
        origenes_ids = {e[0] for e in entidades_origen}
        destinos_ids = {e[0] for e in entidades_destino}
        interseccion = origenes_ids.intersection(destinos_ids)

        if interseccion:
            ent_id = next(iter(interseccion))
            info_ent = [e for e in entidades_origen if e[0] == ent_id][0]
            umbral = info_ent[4] if info_ent[4] is not None else self.config.umbral_exchange_btc
            es_relevante = monto_total_btc >= umbral
            return CalificacionMovimiento(
                es_relevante=es_relevante,
                categoria="TRANSFERENCIA_INTERNA",
                monto_relevante_btc=monto_total_btc,
                umbral_aplicado_btc=umbral,
                entidad_origen_id=ent_id,
                entidad_destino_id=ent_id,
                nivel_confianza=min(info_ent[3], 0.95),
                evidencia=f"Entidad '{info_ent[1]}' identificada en entradas y salidas.",
                limitaciones="Posible reorganización de billeteras frías/calientes o consolidación interna de UTXOs.",
            )

        # 1b. Caso: Consolidación / Auto-transferencia (misma dirección on-chain en entrada y salida)
        dirs_in = {e.direccion_btc for e in tx.entradas if e.direccion_btc}
        dirs_out = {s.direccion_btc for s in tx.salidas if s.direccion_btc}
        interseccion_dirs = dirs_in.intersection(dirs_out)
        if interseccion_dirs:
            dir_comun = next(iter(interseccion_dirs))
            ent_auto = self.servicio_entidades.obtener_o_crear_entidad_ballena(dir_comun)
            umbral = self.config.umbral_desconocido_btc
            es_relevante = monto_total_btc >= umbral
            return CalificacionMovimiento(
                es_relevante=es_relevante,
                categoria="TRANSFERENCIA_INTERNA",
                monto_relevante_btc=monto_total_btc,
                umbral_aplicado_btc=umbral,
                entidad_origen_id=ent_auto.id,
                entidad_destino_id=ent_auto.id,
                nivel_confianza=0.88,
                evidencia=f"Auto-transferencia / Consolidación de UTXO en dirección '{dir_comun[:8]}...{dir_comun[-6:]}'.",
                limitaciones="Reorganización interna de saldos o vuelto de alta cuantía en la misma dirección.",
            )

        # 2. Caso: Entrada a Exchange
        exchanges_destino = [e for e in entidades_destino if e[2] == "Exchange"]
        if exchanges_destino:
            ent_dest = exchanges_destino[0]
            umbral = ent_dest[4] if ent_dest[4] is not None else self.config.umbral_exchange_btc
            ent_orig_id = next(iter(origenes_ids)) if len(origenes_ids) == 1 else None
            if ent_orig_id is None and dirs_in:
                dir_in_p = next(iter(dirs_in))
                ent_orig_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(dir_in_p).id
            es_relevante = monto_total_btc >= umbral
            return CalificacionMovimiento(
                es_relevante=es_relevante,
                categoria="ENTRADA_EXCHANGE",
                monto_relevante_btc=monto_total_btc,
                umbral_aplicado_btc=umbral,
                entidad_origen_id=ent_orig_id,
                entidad_destino_id=ent_dest[0],
                nivel_confianza=ent_dest[3],
                evidencia=f"Flujo hacia dirección atribuida al Exchange '{ent_dest[1]}'.",
                limitaciones=(
                    "Una entrada a exchange NO equivale necesariamente a una venta. "
                    "Puede destinarse a custodia, provisión de liquidez en derivados, colateral o rebalanceo de terceros."
                ),
            )

        # 3. Caso: Salida de Exchange
        exchanges_origen = [e for e in entidades_origen if e[2] == "Exchange"]
        if exchanges_origen:
            ent_orig = exchanges_origen[0]
            umbral = ent_orig[4] if ent_orig[4] is not None else self.config.umbral_exchange_btc
            ent_dest_id = next(iter(destinos_ids)) if len(destinos_ids) == 1 else None
            if ent_dest_id is None and dirs_out:
                dir_out_p = next(iter(dirs_out))
                ent_dest_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(dir_out_p).id
            es_relevante = monto_total_btc >= umbral
            return CalificacionMovimiento(
                es_relevante=es_relevante,
                categoria="SALIDA_EXCHANGE",
                monto_relevante_btc=monto_total_btc,
                umbral_aplicado_btc=umbral,
                entidad_origen_id=ent_orig[0],
                entidad_destino_id=ent_dest_id,
                nivel_confianza=ent_orig[3],
                evidencia=f"Flujo procedente de dirección atribuida al Exchange '{ent_orig[1]}'.",
                limitaciones=(
                    "Una salida de exchange NO equivale necesariamente a una compra spot. "
                    "Puede corresponder a retiros de múltiples usuarios en lote (batching), arbitraje o migración de custodia."
                ),
            )

        # 4. Caso: Movimiento Corporativo / Institucional
        institucionales = [e for e in (list(entidades_origen) + list(entidades_destino)) if e[2] in {"Empresa", "Custodio", "Fondo", "Minero"}]
        if institucionales:
            inst = institucionales[0]
            umbral = inst[4] if inst[4] is not None else self.config.umbral_institucional_btc
            ent_orig_id = next(iter(origenes_ids)) if origenes_ids else None
            ent_dest_id = next(iter(destinos_ids)) if destinos_ids else None
            if ent_orig_id is None and dirs_in:
                ent_orig_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(next(iter(dirs_in))).id
            if ent_dest_id is None and dirs_out:
                ent_dest_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(next(iter(dirs_out))).id
            es_relevante = monto_total_btc >= umbral
            return CalificacionMovimiento(
                es_relevante=es_relevante,
                categoria="MOVIMIENTO_CORPORATIVO",
                monto_relevante_btc=monto_total_btc,
                umbral_aplicado_btc=umbral,
                entidad_origen_id=ent_orig_id,
                entidad_destino_id=ent_dest_id,
                nivel_confianza=inst[3],
                evidencia=f"Intervención de la entidad institucional '{inst[1]}' ({inst[2]}).",
                limitaciones="Transferencia entre custodios institucionales o rebalanceo de reservas.",
            )

        # 5. Caso: Movimiento relevante entre billeteras de gran cuantía (Ballenas)
        umbral_desc = self.config.umbral_desconocido_btc
        es_relevante = monto_total_btc >= umbral_desc
        ent_orig_id = next(iter(origenes_ids)) if origenes_ids else None
        ent_dest_id = next(iter(destinos_ids)) if destinos_ids else None

        if es_relevante:
            if ent_orig_id is None and dirs_in:
                ent_orig_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(next(iter(dirs_in))).id
            if ent_dest_id is None and dirs_out:
                ent_dest_id = self.servicio_entidades.obtener_o_crear_entidad_ballena(next(iter(dirs_out))).id

        return CalificacionMovimiento(
            es_relevante=es_relevante,
            categoria="MOVIMIENTO_CORPORATIVO" if (ent_orig_id and ent_dest_id) else "DESCONOCIDA",
            monto_relevante_btc=monto_total_btc,
            umbral_aplicado_btc=umbral_desc,
            entidad_origen_id=ent_orig_id,
            entidad_destino_id=ent_dest_id,
            nivel_confianza=0.82 if (ent_orig_id or ent_dest_id) else 0.0,
            evidencia=f"Transferencia masiva de {monto_total_btc:,.2f} BTC entre billeteras ballena.",
            limitaciones="Billeteras identificadas on-chain por volumen sin declaración pública corporativa (Principio IV).",
        )

    def registrar_evento_si_relevante(
        self, tx_orm: TransaccionOnChainORM, tx_parsed: TransaccionParsed
    ) -> Optional[EventoAnalizadoORM]:
        """Evalúa y registra en base de datos el evento analizado si supera los umbrales."""
        calificacion = self.evaluar_transaccion(tx_parsed)
        if not calificacion.es_relevante:
            return None

        # Verificar si ya existe evento para este txid
        existente = (
            self.sesion.query(EventoAnalizadoORM)
            .filter(EventoAnalizadoORM.transaccion_id == tx_orm.id)
            .first()
        )
        if existente is not None:
            return existente

        evento = EventoAnalizadoORM(
            transaccion_id=tx_orm.id,
            entidad_origen_id=calificacion.entidad_origen_id,
            entidad_destino_id=calificacion.entidad_destino_id,
            monto_relevante_btc=calificacion.monto_relevante_btc,
            monto_total_salidas_btc=tx_parsed.total_salida_btc,
            umbral_aplicado_btc=calificacion.umbral_aplicado_btc,
            categoria_movimiento=calificacion.categoria,
            nivel_confianza=calificacion.nivel_confianza,
            evidencia=calificacion.evidencia,
            limitaciones=calificacion.limitaciones,
            marca_tiempo_referencia=tx_parsed.marca_tiempo_utc,
            estado_procesamiento="DETECTADO",
        )
        self.sesion.add(evento)
        self.sesion.flush()
        return evento
