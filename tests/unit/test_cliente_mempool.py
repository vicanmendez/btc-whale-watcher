import httpx
from btc_whale_intelligence.clientes_externos.base import ClienteHttpBase
from btc_whale_intelligence.clientes_externos.cliente_mempool import ClienteMempool


def test_cliente_mempool_consultas():
    def manejador(request: httpx.Request) -> httpx.Response:
        ruta = request.url.path
        if ruta.endswith("/blocks/tip/height"):
            return httpx.Response(200, text="890123")
        if ruta.endswith("/block-height/890123"):
            return httpx.Response(200, text="0000000000000000000abc")
        if "/address/" in ruta:
            return httpx.Response(
                200,
                json={
                    "chain_stats": {
                        "funded_txo_sum": 500_000_000,
                        "spent_txo_sum": 100_000_000,
                        "tx_count": 10,
                    }
                },
            )
        return httpx.Response(404)

    cliente_http = ClienteHttpBase("https://mempool.space/api", nombre="mempool", transporte=httpx.MockTransport(manejador))
    cliente = ClienteMempool(cliente_primario=cliente_http)

    assert cliente.obtener_altura_punta() == 890123
    assert cliente.obtener_hash_bloque(890123) == "0000000000000000000abc"
    saldo, conteo = cliente.obtener_saldo_direccion("1DummyAddress")
    assert saldo == 400_000_000
    assert conteo == 10
