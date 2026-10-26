from datetime import date
import httpx
from btc_whale_intelligence.base_datos.modelos import EventoAnalizadoORM, TransaccionOnChainORM
from btc_whale_intelligence.clientes_externos.base import ClienteHttpBase
from btc_whale_intelligence.clientes_externos.cliente_mempool import ClienteMempool
from btc_whale_intelligence.entidades.servicio_entidades import ServicioEntidades
from btc_whale_intelligence.onchain.colector_bloques import ColectorBloques


def test_colector_onchain_idempotencia_y_deteccion(sesion, config):
    # 1. Registrar una entidad conocida (Exchange Binance)
    servicio_ent = ServicioEntidades(sesion)
    servicio_ent.registrar_entidad("Binance", "Exchange", 0.99, "PoR", umbral_personalizado_btc=500)
    servicio_ent.atribuir_direccion(
        "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", "Binance", 0.95, "PoR", date(2026, 1, 1)
    )

    # 2. Mock de Mempool.space devolviendo 1 bloque con 1 tx relevante (800 BTC hacia Binance)
    tx_relevante = {
        "txid": "111122223333444455556666777788889999aaaabbbbccccddddeeeeffff0000",
        "size": 250,
        "weight": 1000,
        "fee": 10000,
        "status": {
            "confirmed": True,
            "block_height": 890120,
            "block_hash": "0000000000000000000blockxyz",
            "block_time": 1700005000,
        },
        "vin": [
            {
                "txid": "orig0000",
                "vout": 0,
                "prevout": {
                    "value": 80_000_010_000,  # 800.0001 BTC
                    "scriptpubkey_address": "1OrigenDesconocido",
                },
            }
        ],
        "vout": [
            {
                "value": 80_000_000_000,  # 800 BTC
                "scriptpubkey_address": "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
            }
        ],
    }

    def manejador(req: httpx.Request) -> httpx.Response:
        ruta = req.url.path
        if ruta.endswith("/blocks/tip/height"):
            return httpx.Response(200, text="890120")
        if "/block-height/" in ruta:
            return httpx.Response(200, text="0000000000000000000blockxyz")
        if "/block/0000000000000000000blockxyz/txs" in ruta:
            return httpx.Response(200, json=[tx_relevante])
        if "/address/" in ruta:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    cliente_mock = ClienteMempool(
        cliente_primario=ClienteHttpBase(
            "https://mempool.space/api", nombre="mock", transporte=httpx.MockTransport(manejador)
        )
    )

    colector = ColectorBloques(sesion, config, cliente_mempool=cliente_mock)

    # Primera sincronización
    eventos = colector.sincronizar()
    assert len(eventos) == 1
    assert eventos[0].categoria_movimiento == "ENTRADA_EXCHANGE"
    assert eventos[0].monto_relevante_btc == 800.0

    total_txs = sesion.query(TransaccionOnChainORM).count()
    assert total_txs == 1

    # Segunda sincronización idéntica (Idempotencia)
    eventos_segunda = colector.sincronizar()
    assert len(eventos_segunda) == 0

    total_txs_despues = sesion.query(TransaccionOnChainORM).count()
    total_eventos_despues = sesion.query(EventoAnalizadoORM).count()
    assert total_txs_despues == 1
    assert total_eventos_despues == 1
