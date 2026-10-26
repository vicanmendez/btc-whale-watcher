from btc_whale_intelligence.onchain.parser_transaccion import parsear_transaccion_esplora


def test_parser_transaccion_confirmada():
    raw_tx = {
        "txid": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
        "size": 225,
        "weight": 900,
        "fee": 5000,
        "status": {
            "confirmed": True,
            "block_height": 890100,
            "block_hash": "0000000000000000000block123",
            "block_time": 1700000000,
        },
        "vin": [
            {
                "txid": "prevtx123",
                "vout": 0,
                "prevout": {
                    "value": 100_000_000,  # 1 BTC
                    "scriptpubkey_address": "1OrigenAddress",
                },
            }
        ],
        "vout": [
            {
                "value": 99_995_000,
                "scriptpubkey_address": "1DestinoAddress",
            }
        ],
    }

    parsed = parsear_transaccion_esplora(raw_tx, altura_actual=890105)
    assert parsed.txid == "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
    assert not parsed.es_mempool
    assert parsed.bloque_altura == 890100
    assert parsed.confirmaciones == 6
    assert parsed.total_entrada_satoshis == 100_000_000
    assert parsed.total_salida_satoshis == 99_995_000
    assert parsed.comision_satoshis == 5000
    assert len(parsed.entradas) == 1
    assert parsed.entradas[0].direccion_btc == "1OrigenAddress"
    assert len(parsed.salidas) == 1
    assert parsed.salidas[0].direccion_btc == "1DestinoAddress"
