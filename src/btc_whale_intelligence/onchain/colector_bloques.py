"""Colector on-chain continuo e idempotente para bloques y mempool (RF-03, RF-05)."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..base_datos.inicializador import obtener_estado_ingesta, registrar_error, registrar_exito_ingesta
from ..base_datos.modelos import (
    DireccionORM,
    EntradaSalidaORM,
    EventoAnalizadoORM,
    TransaccionOnChainORM,
)
from ..clientes_externos.cliente_mempool import ClienteMempool
from ..configuracion import Configuracion
from ..entidades.servicio_entidades import ServicioEntidades
from .detector_movimientos import DetectorMovimientos
from .parser_transaccion import TransaccionParsed, parsear_transaccion_esplora

registro = logging.getLogger(__name__)


class ColectorBloques:
    def __init__(
        self, sesion: Session, config: Configuracion, cliente_mempool: Optional[ClienteMempool] = None
    ) -> None:
        self.sesion = sesion
        self.config = config
        self.cliente = cliente_mempool or ClienteMempool(
            url_primaria=config.url_mempool,
            url_respaldo=config.url_esplora_respaldo,
            intervalo_min_seg=config.onchain_intervalo_min_seg,
        )
        self.servicio_entidades = ServicioEntidades(sesion)
        self.detector = DetectorMovimientos(sesion, config)

    def persistir_transaccion(
        self, tx_parsed: TransaccionParsed
    ) -> tuple[TransaccionOnChainORM, bool]:
        """Persiste una transacción parsed de forma idempotente.

        Retorna (objeto_orm, es_nueva).
        """
        consulta = select(TransaccionOnChainORM).where(TransaccionOnChainORM.txid == tx_parsed.txid)
        existente = self.sesion.scalars(consulta).first()

        if existente is not None:
            # Actualizar confirmaciones o estado de mempool a bloque
            if existente.es_mempool and not tx_parsed.es_mempool:
                existente.es_mempool = False
                existente.bloque_altura = tx_parsed.bloque_altura
                existente.bloque_hash = tx_parsed.bloque_hash
                existente.confirmaciones = tx_parsed.confirmaciones
                existente.marca_tiempo_utc = tx_parsed.marca_tiempo_utc
                self.sesion.flush()
            return existente, False

        tx_orm = TransaccionOnChainORM(
            txid=tx_parsed.txid,
            bloque_altura=tx_parsed.bloque_altura,
            bloque_hash=tx_parsed.bloque_hash,
            marca_tiempo_utc=tx_parsed.marca_tiempo_utc,
            total_entrada_satoshis=tx_parsed.total_entrada_satoshis,
            total_salida_satoshis=tx_parsed.total_salida_satoshis,
            comision_satoshis=tx_parsed.comision_satoshis,
            tamano_bytes=tx_parsed.tamano_bytes,
            peso_vbytes=tx_parsed.peso_vbytes,
            confirmaciones=tx_parsed.confirmaciones,
            es_mempool=tx_parsed.es_mempool,
        )
        self.sesion.add(tx_orm)
        self.sesion.flush()

        # Guardar entradas y salidas
        for ent in tx_parsed.entradas:
            dir_orm = (
                self.servicio_entidades.registrar_o_obtener_direccion(ent.direccion_btc)
                if ent.direccion_btc
                else None
            )
            self.sesion.add(
                EntradaSalidaORM(
                    transaccion_id=tx_orm.id,
                    tipo="ENTRADA",
                    indice=ent.indice,
                    direccion_id=dir_orm.id if dir_orm else None,
                    monto_satoshis=ent.monto_satoshis,
                )
            )

        for sal in tx_parsed.salidas:
            dir_orm = (
                self.servicio_entidades.registrar_o_obtener_direccion(sal.direccion_btc)
                if sal.direccion_btc
                else None
            )
            self.sesion.add(
                EntradaSalidaORM(
                    transaccion_id=tx_orm.id,
                    tipo="SALIDA",
                    indice=sal.indice,
                    direccion_id=dir_orm.id if dir_orm else None,
                    monto_satoshis=sal.monto_satoshis,
                )
            )

        self.sesion.flush()
        return tx_orm, True

    def sincronizar(self) -> list[EventoAnalizadoORM]:
        """Ejecuta un ciclo de sincronización on-chain y retorna nuevos eventos detectados."""
        fuente = "mempool_onchain"
        estado = obtener_estado_ingesta(self.sesion, fuente)
        eventos_nuevos: list[EventoAnalizadoORM] = []

        try:
            altura_punta = self.cliente.obtener_altura_punta()
        except Exception as exc:
            registrar_error(self.sesion, "ColectorBloques", exc, fuente_ingesta=fuente)
            return []

        # Determinar desde qué bloque sincronizar
        if estado.ultimo_bloque_procesado == 0:
            inicio = max(0, altura_punta - 1)
        else:
            inicio = estado.ultimo_bloque_procesado + 1

        limite = min(altura_punta, inicio + self.config.max_bloques_por_ciclo - 1)

        for altura in range(inicio, limite + 1):
            try:
                hash_bloque = self.cliente.obtener_hash_bloque(altura)
                txs_brutas = self.cliente.obtener_todas_transacciones_bloque(hash_bloque)

                for raw_tx in txs_brutas:
                    tx_parsed = parsear_transaccion_esplora(raw_tx, altura_actual=altura_punta)
                    tx_orm, _ = self.persistir_transaccion(tx_parsed)
                    evento = self.detector.registrar_evento_si_relevante(tx_orm, tx_parsed)
                    if evento is not None and evento not in eventos_nuevos:
                        eventos_nuevos.append(evento)

                estado.ultimo_bloque_procesado = altura
                estado.ultimo_hash_procesado = hash_bloque
                self.sesion.flush()
                registro.info("Bloque sincronizado: %d (%s) con %d txs", altura, hash_bloque[:12], len(txs_brutas))

            except Exception as exc:
                registrar_error(
                    self.sesion,
                    "ColectorBloques",
                    exc,
                    contexto={"altura": altura},
                    fuente_ingesta=fuente,
                )
                break

        # Opcional: Mempool para direcciones catalogadas activas
        if self.config.vigilar_mempool_direcciones:
            try:
                direcciones_activas = self.sesion.scalars(
                    select(DireccionORM.direccion_btc)
                    .join(DireccionORM.atribuciones)
                    .where(DireccionORM.atribuciones.any())
                    .limit(self.config.max_direcciones_por_ciclo)
                ).all()

                for dir_btc in direcciones_activas:
                    txs_dir = self.cliente.obtener_transacciones_direccion(dir_btc)
                    for raw_tx in txs_dir:
                        if not raw_tx.get("status", {}).get("confirmed", False):
                            tx_parsed = parsear_transaccion_esplora(raw_tx, altura_actual=altura_punta)
                            tx_orm, _ = self.persistir_transaccion(tx_parsed)
                            ev = self.detector.registrar_evento_si_relevante(tx_orm, tx_parsed)
                            if ev is not None and ev not in eventos_nuevos:
                                eventos_nuevos.append(ev)

            except Exception as exc:
                registrar_error(self.sesion, "ColectorMempool", exc, fuente_ingesta=fuente)

        registrar_exito_ingesta(self.sesion, fuente)
        return eventos_nuevos
