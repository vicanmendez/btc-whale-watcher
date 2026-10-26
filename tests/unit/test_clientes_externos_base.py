import httpx
import pytest

from btc_whale_intelligence.clientes_externos.base import ClienteHttpBase, ErrorProveedorExterno


class RelojFalso:
    def __init__(self):
        self.t = 0.0
        self.esperas = []

    def reloj(self):
        return self.t

    def dormir(self, s):
        self.esperas.append(s)
        self.t += s


def _cliente(manejador, reloj=None, **kw):
    reloj = reloj or RelojFalso()
    return ClienteHttpBase(
        "https://api.prueba", nombre="prueba", transporte=httpx.MockTransport(manejador),
        dormir=reloj.dormir, reloj=reloj.reloj, espera_base_seg=1.0, **kw
    ), reloj


def test_reintenta_429_y_respeta_retry_after():
    respuestas = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={"ok": 1})])
    cliente, reloj = _cliente(lambda req: next(respuestas))
    assert cliente.obtener_json("/x") == {"ok": 1}
    assert reloj.esperas == [7.0]


def test_reintenta_errores_de_red_con_retroceso_exponencial():
    llamadas = {"n": 0}

    def manejador(req):
        llamadas["n"] += 1
        if llamadas["n"] < 3:
            raise httpx.ConnectError("caida", request=req)
        return httpx.Response(200, text=" 123 ")

    cliente, reloj = _cliente(manejador)
    assert cliente.obtener_texto("/altura") == "123"
    assert len(reloj.esperas) == 2
    assert 1.0 <= reloj.esperas[0] < 2.0 and 2.0 <= reloj.esperas[1] < 3.0


def test_reintentos_acotados():
    cliente, reloj = _cliente(lambda req: httpx.Response(503), max_reintentos=2)
    with pytest.raises(ErrorProveedorExterno) as exc:
        cliente.obtener_json("/x")
    assert exc.value.codigo_http == 503
    assert len(reloj.esperas) == 2


def test_no_reintenta_4xx_no_reintentable():
    cliente, reloj = _cliente(lambda req: httpx.Response(451))
    with pytest.raises(ErrorProveedorExterno) as exc:
        cliente.obtener_json("/x")
    assert exc.value.codigo_http == 451 and not exc.value.reintentable
    assert reloj.esperas == []


def test_respeta_intervalo_minimo_entre_peticiones():
    cliente, reloj = _cliente(lambda req: httpx.Response(200, json=[]), intervalo_minimo_seg=0.5)
    cliente.obtener_json("/a")
    cliente.obtener_json("/b")
    assert reloj.esperas == [0.5]


def test_json_invalido_es_error_controlado():
    cliente, _ = _cliente(lambda req: httpx.Response(200, text="<html>"))
    with pytest.raises(ErrorProveedorExterno):
        cliente.obtener_json("/x")
