"""Cabeçalhos de segurança em toda resposta do Painel (auditoria 07/11/2026)."""
import http.client
import threading
import types
from http.server import ThreadingHTTPServer

import app_servidor

ESPERADOS = {"x-content-type-options": "nosniff", "x-frame-options": "SAMEORIGIN", "referrer-policy": "no-referrer",
             "cross-origin-resource-policy": "same-origin"}


def _pedir(porta, caminho, host=None, token=None):
    cab = {"Host": host or f"127.0.0.1:{app_servidor.PORTA}", **({"X-Token": token} if token else {})}
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    c.request("GET", caminho, headers=cab)
    r = c.getresponse()
    r.read()
    return r.status, {k.lower(): v for k, v in r.getheaders()}


def test_toda_resposta_leva_os_cabecalhos_de_seguranca_inclusive_os_erros():
    estado = types.SimpleNamespace(marca_tela=lambda: "v1", so_ver=False, demo=True, atualizar=lambda: None)
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), app_servidor.criar_handler(estado, {}, "token-de-teste", [0]))
    porta = servidor.server_address[1]
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        casos = [("/", None, None, 200), ("/painel.js", None, None, 200), ("/api/versao", None, "token-de-teste", 200),
                 ("/api/versao", None, "errado", 403), ("/api/versao", "outro-site.com", "token-de-teste", 403)]
        for caminho, host, token, status in casos:
            s, h = _pedir(porta, caminho, host, token)
            assert s == status, (caminho, s)
            for nome, valor in ESPERADOS.items():
                assert h.get(nome) == valor, (caminho, nome, h.get(nome))
    finally:
        servidor.shutdown()
        servidor.server_close()
