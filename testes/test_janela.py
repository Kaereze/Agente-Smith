"""Peça única da janela por cima (usuário, 21/10/2026, desenho Pr7): cinza do modo Outlook + animação nova, uma só
para todas as janelas."""
import re
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "app_ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
CSS = (UI / "pecas" / "janela.css").read_text(encoding="utf-8")
JS = (UI / "pecas" / "janela.js").read_text(encoding="utf-8")


def test_a_peca_entra_na_pagina():
    assert '<link rel="stylesheet" href="/pecas/janela.css">' in HTML and '<script src="/pecas/janela.js"></script>' in HTML


def test_janelas_no_cinza_e_sem_o_verde_antigo():
    assert ".modal-fundo,.janela-saindo,.visor-fundo,body > .toast,body > .carregando{" in CSS and "--folha:#262626" in CSS
    regra = re.search(r"\.modal-fundo\{[^}]*\}", HTML).group(0)
    assert "rgba(7,20,17" not in regra and "animation" not in regra   # cor e animação só na peça
    parada = HTML.split(".tela-parada{")[1].split("}")[0]
    assert "#0f2e2a" not in parada and "#1f1f1f" in parada


def test_uma_animacao_so_para_abrir_e_fechar():
    for nome in ("janelaEntra", "janelaSai", "janelaFundo", "janelaFundoSai", "janelaAviso"):
        assert CSS.count(f"@keyframes {nome}{{") == 1
        assert f"@keyframes {nome}" not in HTML   # nenhuma cópia fora da peça
    assert "prefers-reduced-motion" in CSS


def test_saida_animada_troca_a_classe_antes_de_tirar():
    assert 'classList.replace("modal-fundo", "janela-saindo")' in JS and "JANELA_SAIDA_MS = 150" in JS
    assert 'n.classList?.contains("janela-saindo")' in HTML   # o foco volta também na saída animada
