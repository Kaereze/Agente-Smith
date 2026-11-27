"""Tela nova em React (27/11/2026): o servidor abre /v2/ com a senha da sessão, entrega os arquivos montados (app_ui/v2/assets),
recusa caminhos estranhos, mantém a tela de hoje em /classica e só troca "/" quando o interruptor "tela": "react" estiver ligado.
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

V2 = app_servidor.PASTA_UI / "v2"
pytestmark = pytest.mark.skipif(not (V2 / "index.html").is_file(), reason="tela nova ainda não montada (cd app_react; npm run build)")


def _subir(tmp_path, mp, tela=""):
    for nome, arq in (("CAMINHO_CACHE", "cache.pkl"), ("CAMINHO_PREFS", "app.json"), ("CAMINHO_CANCELADAS", "canceladas.json")):
        mp.setattr(app_servidor, nome, tmp_path / arq)
    cfg = demo.configurar_cfg(carregar_config(exigir_chave=False))
    if tela:
        cfg["tela"] = tela
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


def test_v2_abre_a_tela_nova_com_a_senha_da_sessao(servidor):
    st, tipo, html = _get(servidor, "/v2/")
    assert st == 200 and "text/html" in tipo
    assert 'content="senha-de-teste"' in html and "__TOKEN__" not in html
    assert 'id="raiz"' in html


def test_os_arquivos_montados_sao_entregues_e_caminho_estranho_e_recusado(servidor):
    _, _, html = _get(servidor, "/v2/")
    arquivos = re.findall(r'(/v2/assets/[A-Za-z0-9_.-]+\.(?:js|css))', html)
    assert arquivos, "o index da tela nova precisa apontar para os arquivos montados"
    for a in arquivos:
        st, tipo, corpo = _get(servidor, a)
        assert st == 200 and corpo and ("javascript" in tipo or "css" in tipo)
    for ruim in ("/v2/assets/../index.html", "/v2/assets/%2e%2e/x.js", "/v2/assets/nao-existe.js", "/v2/assets/x.py"):
        assert _get(servidor, ruim)[0] != 200, ruim


def test_a_tela_de_hoje_continua_em_barra_e_em_classica(servidor):
    for caminho in ("/", "/classica"):
        st, _, html = _get(servidor, caminho)
        assert st == 200 and 'class="app modo-ol' in html and 'name="painel-token"' not in html


def test_interruptor_react_troca_so_a_barra(tmp_path):
    mp = pytest.MonkeyPatch()
    srv, base = _subir(tmp_path, mp, tela="react")
    try:
        assert 'name="painel-token"' in _get(base, "/")[2]
        assert 'class="app modo-ol' in _get(base, "/classica")[2]   # a reserva continua a um clique
    finally:
        srv.shutdown()
        srv.server_close()
        mp.undo()


def test_interruptor_so_aceita_react():
    assert app_servidor.tela_react({"tela": "react"}) and app_servidor.tela_react({"tela": " React "})
    assert not app_servidor.tela_react({}) and not app_servidor.tela_react({"tela": "classica"}) and not app_servidor.tela_react(None)
