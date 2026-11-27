"""A tela do Painel em React (27/11/2026): o servidor abre a tela montada (app_ui/v2) em "/" com a senha da sessão, entrega os
arquivos montados e os ajustes, recusa caminhos estranhos e não serve mais nada da tela de antes (apagada em 27/11/2026).
Sem navegador: só o servidor, numa porta livre, no modo demonstração (dados fictícios)."""
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import app_servidor
from config import carregar_config
from painel import demo

pytestmark = pytest.mark.skipif(not (app_servidor.PASTA_TELA / "index.html").is_file(), reason="tela ainda não montada (cd app_react; npm run build)")


def _subir(tmp_path, mp):
    for nome, arq in (("CAMINHO_CACHE", "cache.pkl"), ("CAMINHO_PREFS", "app.json"), ("CAMINHO_CANCELADAS", "canceladas.json")):
        mp.setattr(app_servidor, nome, tmp_path / arq)
    cfg = demo.configurar_cfg(carregar_config(exigir_chave=False))
    backend = demo.BackendDemo()
    estado = app_servidor.Estado(backend, cfg)
    demo.preparar(estado, backend)
    estado.demo, estado.so_ver = True, False
    reserva = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
    porta = reserva.server_address[1]
    reserva.server_close()
    mp.setattr(app_servidor, "PORTA", porta)
    estado.uso_ref = [-1e9]
    srv = ThreadingHTTPServer(("127.0.0.1", porta), app_servidor.criar_handler(estado, cfg, "senha-de-teste", estado.uso_ref))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{porta}"


def _get(base, caminho):
    try:
        r = urllib.request.urlopen(urllib.request.Request(base + caminho), timeout=20)
        return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", ""


@pytest.fixture
def servidor(tmp_path):
    mp = pytest.MonkeyPatch()
    srv, base = _subir(tmp_path, mp)
    yield base
    srv.shutdown()
    srv.server_close()
    mp.undo()


def test_a_tela_abre_em_barra_com_a_senha_da_sessao(servidor):
    for caminho in ("/", "/index.html", "/v2/"):   # /v2/ fica por compatibilidade
        st, tipo, html = _get(servidor, caminho)
        assert st == 200 and "text/html" in tipo, caminho
        assert 'content="senha-de-teste"' in html and "__TOKEN__" not in html and 'id="raiz"' in html
        assert '<script src="/ajustes.js"></script>' in html   # os tempos do ajustes.json chegam antes da tela


def test_os_arquivos_montados_sao_entregues_e_caminho_estranho_e_recusado(servidor):
    _, _, html = _get(servidor, "/")
    arquivos = re.findall(r'(/v2/assets/[A-Za-z0-9_.-]+\.(?:js|css))', html)
    assert arquivos, "o index da tela precisa apontar para os arquivos montados"
    for a in arquivos:
        st, tipo, corpo = _get(servidor, a)
        assert st == 200 and corpo and ("javascript" in tipo or "css" in tipo)
    for ruim in ("/v2/assets/../index.html", "/v2/assets/%2e%2e/x.js", "/v2/assets/nao-existe.js", "/v2/assets/x.py"):
        assert _get(servidor, ruim)[0] != 200, ruim


def test_a_tela_de_antes_nao_existe_mais(servidor):
    for caminho in ("/classica", "/telas.js", "/estilo.css", "/pecas/carregando.js", "/fontes/fontes.css"):
        assert _get(servidor, caminho)[0] != 200, caminho
    assert not (app_servidor.PASTA_UI / "index.html").exists() and not (app_servidor.PASTA_UI / "pecas").exists()


def test_ajustes_e_icone_continuam(servidor):
    st, tipo, js = _get(servidor, "/ajustes.js")
    assert st == 200 and "javascript" in tipo and "window.aj = " in js
    assert _get(servidor, "/icone.png")[0] == 200


def test_marca_da_pagina_acompanha_a_tela_montada():
    assert app_servidor._marca_pagina().isdigit()   # mudou a tela no disco = a janela aberta recarrega sozinha
