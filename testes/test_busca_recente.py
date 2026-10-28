"""Histórico da pesquisa (28/10/2026): últimas 24 h, só neste PC, sem CPF/CNPJ."""
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "app_ui"
JS = (UI / "pecas" / "busca_recente.js").read_text(encoding="utf-8")
CSS = (UI / "pecas" / "busca_recente.css").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")


def test_peca_entra_na_pagina_depois_da_caixa_de_busca():
    assert '<link rel="stylesheet" href="/pecas/busca_recente.css">' in HTML and '<script src="/pecas/busca_recente.js"></script>' in HTML
    assert HTML.index('id="busca"') < HTML.index('<script src="/pecas/busca_recente.js"></script>')   # a caixa já existe quando a peça roda


def test_guarda_so_24_horas_e_so_neste_navegador():
    assert "VALIDADE_MS = 24 * 3600 * 1000" in JS and 'CHAVE = "painel.buscas"' in JS and "localStorage" in JS
    assert "api(" not in JS and "fetch(" not in JS and "XMLHttpRequest" not in JS   # nada vai ao servidor, à planilha ou a outro PC
    assert "ler();   // ao abrir o Painel já apaga o que passou de 24 h" in JS       # reseta sozinho


def test_nao_guarda_cpf_cnpj_nem_texto_curto():
    assert "pareceDocumento" in JS and "d.length === 11 || d.length === 14" in JS
    assert "t.length < 3 || pareceDocumento(t)" in JS


def test_lista_tem_limpar_remover_e_teclado():
    assert "data-bh-limpar" in JS and "data-bh-x" in JS and "ArrowDown" in JS and "Escape" in JS
    assert ".bh-it.on" in CSS and ".modo-ol .bh" in CSS and "prefers-reduced-motion" in CSS
