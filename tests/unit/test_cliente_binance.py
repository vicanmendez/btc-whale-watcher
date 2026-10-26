import httpx
from btc_whale_intelligence.clientes_externos.base import ClienteHttpBase
from btc_whale_intelligence.clientes_externos.cliente_binance import ClienteBinance


def test_cliente_binance_consultas():
    def manejador(request: httpx.Request) -> httpx.Response:
        ruta = request.url.path
        if ruta.endswith("/ticker/price"):
            return httpx.Response(200, json={"symbol": "BTCUSDT", "price": "68500.50"})
        if ruta.endswith("/ticker/24hr"):
            return httpx.Response(
                200,
                json={
                    "lastPrice": "68500.50",
                    "priceChangePercent": "2.45",
                    "volume": "15420.5",
                    "quoteVolume": "1056304250.0",
                    "count": 1250000,
                },
            )
        if ruta.endswith("/klines"):
            return httpx.Response(
                200,
                json=[
                    [1700000000000, "68000", "68600", "67900", "68500", "500.5", 1700003599999, "34000000", 25000]
                ],
            )
        return httpx.Response(404)

    cliente_http = ClienteHttpBase("https://data-api.binance.vision/api/v3", nombre="binance", transporte=httpx.MockTransport(manejador))
    cliente = ClienteBinance(cliente_http=cliente_http)

    assert cliente.obtener_precio_actual() == 68500.50
    resumen = cliente.obtener_resumen_24h()
    assert resumen["variacion_24h_pct"] == 2.45
    assert resumen["volumen_btc"] == 15420.5

    velas = cliente.obtener_velas()
    assert len(velas) == 1
    assert velas[0]["precio_cierre"] == 68500.0
