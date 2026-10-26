"""Cliente REST para Mempool.space con respaldo en Blockstream Esplora (RF-03)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .base import ClienteHttpBase, ErrorProveedorExterno

registro = logging.getLogger(__name__)


class ClienteMempool:
    """Cliente para la API Esplora de Mempool.space con fallback automático."""

    def __init__(
        self,
        url_primaria: str = "https://mempool.space/api",
        url_respaldo: Optional[str] = "https://blockstream.info/api",
        intervalo_min_seg: float = 0.5,
        cliente_primario: Optional[ClienteHttpBase] = None,
        cliente_respaldo: Optional[ClienteHttpBase] = None,
    ) -> None:
        self._primario = cliente_primario or ClienteHttpBase(
            url_primaria,
            nombre="Mempool.space",
            intervalo_minimo_seg=intervalo_min_seg,
        )
        self._respaldo = (
            cliente_respaldo
            or (
                ClienteHttpBase(
                    url_respaldo,
                    nombre="Blockstream Esplora",
                    intervalo_minimo_seg=intervalo_min_seg,
                )
                if url_respaldo
                else None
            )
        )

    def cerrar(self) -> None:
        self._primario.cerrar()
        if self._respaldo:
            self._respaldo.cerrar()

    def _ejecutar(self, metodo: str, *args, **kwargs) -> Any:
        try:
            return getattr(self._primario, metodo)(*args, **kwargs)
        except ErrorProveedorExterno as exc:
            if self._respaldo and exc.reintentable:
                registro.warning(
                    "Fallo en fuente primaria Mempool.space (%s); activando respaldo Esplora",
                    exc,
                )
                return getattr(self._respaldo, metodo)(*args, **kwargs)
            raise

    def obtener_altura_punta(self) -> int:
        texto = self._ejecutar("obtener_texto", "/blocks/tip/height")
        return int(texto)

    def obtener_hash_bloque(self, altura: int) -> str:
        return self._ejecutar("obtener_texto", f"/block-height/{altura}")

    def obtener_bloque(self, hash_bloque: str) -> dict[str, Any]:
        return self._ejecutar("obtener_json", f"/block/{hash_bloque}")

    def obtener_transacciones_bloque(
        self, hash_bloque: str, indice_inicio: int = 0
    ) -> list[dict[str, Any]]:
        """Obtiene hasta 25 transacciones por página a partir de `indice_inicio`."""
        if indice_inicio == 0:
            return self._ejecutar("obtener_json", f"/block/{hash_bloque}/txs")
        return self._ejecutar("obtener_json", f"/block/{hash_bloque}/txs/{indice_inicio}")

    def obtener_todas_transacciones_bloque(
        self, hash_bloque: str, max_transacciones: int = 500
    ) -> list[dict[str, Any]]:
        """Descarga transacciones paginadas del bloque hasta `max_transacciones`."""
        todas: list[dict[str, Any]] = []
        indice = 0
        while len(todas) < max_transacciones:
            lote = self.obtener_transacciones_bloque(hash_bloque, indice)
            if not lote:
                break
            todas.extend(lote)
            if len(lote) < 25:
                break
            indice += len(lote)
        return todas[:max_transacciones]

    def obtener_transaccion(self, txid: str) -> dict[str, Any]:
        return self._ejecutar("obtener_json", f"/tx/{txid}")

    def obtener_saldo_direccion(self, direccion_btc: str) -> tuple[int, int]:
        """Retorna (saldo_satoshis, conteo_txs) sumando confirmados."""
        datos = self._ejecutar("obtener_json", f"/address/{direccion_btc}")
        confirmados = datos.get("chain_stats", {})
        fondos = confirmados.get("funded_txo_sum", 0)
        gastados = confirmados.get("spent_txo_sum", 0)
        conteo = confirmados.get("tx_count", 0)
        return max(0, fondos - gastados), conteo

    def obtener_transacciones_direccion(
        self, direccion_btc: str
    ) -> list[dict[str, Any]]:
        return self._ejecutar("obtener_json", f"/address/{direccion_btc}/txs")

    def obtener_mempool_reciente(self) -> list[dict[str, Any]]:
        return self._ejecutar("obtener_json", "/mempool/recent")
