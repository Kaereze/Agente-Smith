"""Tamanho da tela (19/11/2026): o Painel escolhe o zoom pela largura e pela escala daquele PC; o Python aplica no WebView2."""
import sys
import types
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


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


