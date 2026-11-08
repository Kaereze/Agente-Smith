"""Endurecimento do servidor local (08/11/2026): token comparado em tempo constante, teto do corpo do pedido e cliente que sai no meio da resposta."""
import http.client
import threading
import types
from http.server import ThreadingHTTPServer

import app_servidor


def _servidor():
    estado = types.SimpleNamespace(marca_tela=lambda: "v1", so_ver=False, demo=True, atualizar=lambda: None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app_servidor.criar_handler(estado, {}, "token-de-teste", [0]))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _post(porta, caminho, corpo=b"{}", extra=None, token="token-de-teste"):
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    cab = {"Host": f"127.0.0.1:{app_servidor.PORTA}", "X-Token": token, **(extra or {})}
    c.request("POST", caminho, body=corpo, headers=cab)
    r = c.getresponse()
    r.read()
    return r.status


def test_token_errado_ou_sem_token_continua_barrado_e_o_certo_passa():
    srv, porta = _servidor()
    try:
        assert _post(porta, "/api/tema", b'{"tema": "dark"}', token="errado") == 403
        assert _post(porta, "/api/tema", b'{"tema": "dark"}', token="") == 403
        assert _post(porta, "/api/tema", b'{"tema": "invalido"}') == 400   # passou do token; recusou o valor
    finally:
        srv.shutdown()
        srv.server_close()


def test_pedido_maior_que_o_teto_e_recusado_sem_ler_o_corpo():
    srv, porta = _servidor()
    try:
        assert _post(porta, "/api/tema", b"{}", extra={"Content-Length": str(app_servidor.CORPO_MAXIMO_BYTES + 1)}) == 413
        assert _post(porta, "/api/tema", b"{}", extra={"Content-Length": "abc"}) == 400
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_comparacao_do_token_e_em_tempo_constante():
    fonte = open(app_servidor.__file__, encoding="utf-8").read()
    assert "hmac.compare_digest(str(self.headers.get(\"X-Token\")" in fonte and 'get("X-Token") == token' not in fonte


def test_cliente_que_fecha_no_meio_da_resposta_nao_vira_erro_no_log():
    fonte = open(app_servidor.__file__, encoding="utf-8").read()
    assert "except (ConnectionError, TimeoutError)" in fonte
