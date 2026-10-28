"""Respostas do Painel comprimidas (auditoria 27/10/2026): /api/estado tinha 1,8 MB e /api/correio 1,5 MB sem compressão."""
import gzip
import http.client
import json
import threading
import types
from http.server import ThreadingHTTPServer

import app_servidor


def test_so_comprime_quando_o_navegador_aceita_e_o_corpo_e_grande():
    grande = b"x" * 5000
    assert app_servidor.comprimir_se_vale(grande, "gzip, deflate, br")[1] is True
    assert gzip.decompress(app_servidor.comprimir_se_vale(grande, "gzip")[0]) == grande
    assert app_servidor.comprimir_se_vale(grande, "")[1] is False
    assert app_servidor.comprimir_se_vale(grande, None)[1] is False
    assert app_servidor.comprimir_se_vale(b"pequeno", "gzip") == (b"pequeno", False)


def _pedir(porta, caminho, aceita=None, extra=None):
    cab = {"Host": f"127.0.0.1:{app_servidor.PORTA}", **(extra or {})}
    if aceita:
        cab["Accept-Encoding"] = aceita
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    c.request("GET", caminho, headers=cab)
    r = c.getresponse()
    corpo = r.read()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, corpo


def test_servidor_de_verdade_manda_gzip_na_pagina_e_na_api():
    estado = types.SimpleNamespace(marca_tela=lambda: "v1", so_ver=False, demo=True, atualizar=lambda: None)
    handler = app_servidor.criar_handler(estado, {}, "token-de-teste", [0])
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    porta = servidor.server_address[1]
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        # página inicial (grande): comprimida só para quem aceita, e igual depois de descomprimir
        s1, h1, c1 = _pedir(porta, "/", aceita="gzip")
        s2, h2, c2 = _pedir(porta, "/")
        assert s1 == s2 == 200
        assert h1.get("content-encoding") == "gzip" and "content-encoding" not in h2
        assert gzip.decompress(c1) == c2 and len(c1) < len(c2) / 3
        assert int(h1["content-length"]) == len(c1)
        # JS estático
        s3, h3, c3 = _pedir(porta, "/painel.js", aceita="gzip")
        assert h3.get("content-encoding") == "gzip" and b"function" in gzip.decompress(c3)
        # API pequena (< 1 KB): sem compressão, JSON intacto
        s4, h4, c4 = _pedir(porta, "/api/versao", aceita="gzip", extra={"X-Token": "token-de-teste"})
        assert s4 == 200 and "content-encoding" not in h4 and json.loads(c4) == {"v": "v1"}
    finally:
        servidor.shutdown()
        servidor.server_close()
