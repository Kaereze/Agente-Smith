"""Um servidor do Painel por PC (21/10/2026): dois Painéis vivos leriam a mesma fila e poderiam mandar o mesmo e-mail duas vezes."""
import sys

import pytest

import app_servidor


@pytest.mark.skipif(sys.platform != "win32", reason="trava do Windows")
def test_segundo_painel_no_mesmo_pc_nao_sobe(tmp_path, monkeypatch):
    monkeypatch.setattr(app_servidor, "PASTA_ESTADO", tmp_path)
    primeiro = app_servidor.travar_instancia_unica()
    assert primeiro is not None
    assert app_servidor.travar_instancia_unica() is None          # aberto quase junto: não sobe
    primeiro.close()                                              # o primeiro fechou (ou morreu)
    terceiro = app_servidor.travar_instancia_unica()
    assert terceiro is not None
    terceiro.close()


@pytest.mark.skipif(sys.platform != "win32", reason="trava do Windows")
def test_main_sai_sem_subir_quando_ja_tem_painel(tmp_path, monkeypatch):
    monkeypatch.setattr(app_servidor, "PASTA_ESTADO", tmp_path)
    monkeypatch.setattr(app_servidor, "porta_livre", lambda: True)   # a porta parece livre (a brecha de antes)
    abertas = []
    monkeypatch.setattr(app_servidor, "abrir_janela", lambda: abertas.append(1))
    monkeypatch.setattr(sys, "argv", ["app_servidor.py"])
    outro = app_servidor.travar_instancia_unica()                 # o outro Painel já está de pé
    try:
        assert app_servidor.main() == 0 and abertas == [1]        # só mostra a janela do que já roda
    finally:
        outro.close()
