"""Tamanho da tela (19/11/2026): o Painel escolhe o zoom pela largura e pela escala daquele PC; o Python aplica no WebView2."""
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def _calcular_no_node(larguras):
    js = (RAIZ / "app_ui" / "pecas" / "escala.js").read_text(encoding="utf-8")
    roteiro = ("global.window={addEventListener(){},innerWidth:1,pywebview:undefined};global.document={addEventListener(){}};"
               "global.localStorage={getItem(){return null},setItem(){}};" + js +
               f";console.log(JSON.stringify({json.dumps(larguras)}.map(w=>window.painelEscala.calcular(w))))")
    saida = subprocess.run(["node", "-e", roteiro], capture_output=True, text=True, timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="precisa do Node para rodar o JavaScript")
def test_zoom_automatico_segue_a_largura_com_limites():
    # 1000 px (notebook com escala de 150%) -> 0,85 (piso) · 1280 -> 0,85 · 1440 -> 0,95 · 1500 -> 1 · 1920 -> 1,3 (teto) · 3840 -> 1,3
    assert _calcular_no_node([1000, 1280, 1440, 1500, 1920, 3840]) == [0.85, 0.85, 0.95, 1.0, 1.3, 1.3]


def test_python_limita_e_aplica_o_zoom_na_linha_da_janela(monkeypatch):
    import app_janela

    class _Web:
        ZoomFactor = 1.0

        class CoreWebView2:
            class Settings:
                IsZoomControlEnabled = True

    web = _Web()
    form = types.SimpleNamespace(webview=web, Invoke=lambda acao: acao())
    monkeypatch.setitem(app_janela.ESTADO, "janela", types.SimpleNamespace(native=form))
    monkeypatch.setitem(sys.modules, "System", types.SimpleNamespace(Action=lambda f: f))
    api = app_janela.Api()
    assert api.definir_escala(1.1) == 1.1 and web.ZoomFactor == 1.1
    assert web.CoreWebView2.Settings.IsZoomControlEnabled is False                 # o zoom solto (Ctrl + e -) fica desligado
    assert api.definir_escala(9) == 1.5 and api.definir_escala(0.1) == 0.75        # nunca passa dos limites
    assert api.definir_escala("lixo") == 0.75                                      # valor inválido não muda nada
    assert api.escala_atual() == 0.75


def test_sem_janela_a_escala_volta_ao_normal(monkeypatch):
    import app_janela
    monkeypatch.setitem(app_janela.ESTADO, "janela", None)
    api = app_janela.Api()
    assert api.escala_atual() == 1.0 and api.definir_escala(1.2) == 1.0


def test_o_controle_aparece_no_menu_e_esta_carregado_na_tela():
    html = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")
    assert "/pecas/escala.js" in html and "/pecas/escala.css" in html
    assert html.index("/pecas/escala.js") < html.index("/telas_janela.js")           # o menu do operador usa o painelEscala
    assert "window.painelEscala" in (RAIZ / "app_ui" / "telas_janela.js").read_text(encoding="utf-8")
