"""Parser y normalizador de transacciones brutas de Bitcoin (Esplora API)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class EntradaParsed:
    indice: int
    txid_anterior: Optional[str]
    vout_anterior: Optional[int]
    direccion_btc: Optional[str]
    monto_satoshis: int


@dataclass(frozen=True)
class SalidaParsed:
    indice: int
    direccion_btc: Optional[str]
    monto_satoshis: int


@dataclass(frozen=True)
class TransaccionParsed:
    txid: str
    bloque_altura: Optional[int]
    bloque_hash: Optional[str]
    marca_tiempo_utc: datetime
    total_entrada_satoshis: int
    total_salida_satoshis: int
    comision_satoshis: int
    tamano_bytes: int
    peso_vbytes: int
    confirmaciones: int
    es_mempool: bool
    entradas: tuple[EntradaParsed, ...]
    salidas: tuple[SalidaParsed, ...]

    @property
    def total_salida_btc(self) -> float:
        return self.total_salida_satoshis / 100_000_000.0


def parsear_transaccion_esplora(
    datos: dict[str, Any], altura_actual: Optional[int] = None
) -> TransaccionParsed:
    """Convierte el formato JSON de Esplora a TransaccionParsed validado."""
    txid = datos["txid"].strip().lower()
    tamano = int(datos.get("size", 0))
    peso = int(datos.get("weight", tamano * 4))
    vbytes = max(1, (peso + 3) // 4)

    estado = datos.get("status", {})
    confirmado = bool(estado.get("confirmed", False))
    bloque_altura = estado.get("block_height") if confirmado else None
    bloque_hash = estado.get("block_hash") if confirmado else None

    if confirmado and "block_time" in estado:
        marca_tiempo = datetime.fromtimestamp(estado["block_time"], tz=timezone.utc)
    else:
        marca_tiempo = datetime.now(timezone.utc)

    entradas: list[EntradaParsed] = []
    total_entradas = 0
    for idx, vin in enumerate(datos.get("vin", [])):
        prevout = vin.get("prevout") or {}
        monto = int(prevout.get("value", 0))
        total_entradas += monto
        dir_btc = prevout.get("scriptpubkey_address")
        entradas.append(
            EntradaParsed(
                indice=idx,
                txid_anterior=vin.get("txid"),
                vout_anterior=vin.get("vout"),
                direccion_btc=dir_btc.strip() if dir_btc else None,
                monto_satoshis=monto,
            )
        )

    salidas: list[SalidaParsed] = []
    total_salidas = 0
    for idx, vout in enumerate(datos.get("vout", [])):
        monto = int(vout.get("value", 0))
        total_salidas += monto
        dir_btc = vout.get("scriptpubkey_address")
        salidas.append(
            SalidaParsed(
                indice=idx,
                direccion_btc=dir_btc.strip() if dir_btc else None,
                monto_satoshis=monto,
            )
        )

    comision = datos.get("fee")
    if comision is None:
        comision = max(0, total_entradas - total_salidas) if total_entradas > 0 else 0
    else:
        comision = int(comision)

    confirmaciones = 0
    if confirmado and bloque_altura is not None and altura_actual is not None:
        confirmaciones = max(1, altura_actual - bloque_altura + 1)
    elif confirmado:
        confirmaciones = 1

    return TransaccionParsed(
        txid=txid,
        bloque_altura=bloque_altura,
        bloque_hash=bloque_hash,
        marca_tiempo_utc=marca_tiempo,
        total_entrada_satoshis=total_entradas,
        total_salida_satoshis=total_salidas,
        comision_satoshis=comision,
        tamano_bytes=tamano,
        peso_vbytes=vbytes,
        confirmaciones=confirmaciones,
        es_mempool=not confirmado,
        entradas=tuple(entradas),
        salidas=tuple(salidas),
    )
