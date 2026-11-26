"""Tema claro do Painel (26/11/2026): ferramentas/gerar_tema_claro.py gera app_ui/pecas/tema_claro.css a partir do desenho escuro.
Antes, o botão de tema só trocava a palavra: as cores do modo Outlook estavam fixas no CSS e a tela continuava escura."""
import colorsys
import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gerar_tema_claro", RAIZ / "ferramentas" / "gerar_tema_claro.py")
gerador = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gerador)

CSS = RAIZ / "app_ui" / "pecas" / "tema_claro.css"


def _luz(cor):
    r, g, b, a = gerador.ler_cor(cor)
    return colorsys.rgb_to_hls(r, g, b)[1], a


def test_arquivo_em_dia_com_os_estilos():
    """Mudou um estilo do modo escuro e esqueceu de rodar o gerador: o tema claro ficaria velho."""
    assert CSS.read_text(encoding="utf-8") == gerador.gerar(), "rode: python ferramentas/gerar_tema_claro.py"


def test_pagina_carrega_o_tema_claro_por_ultimo():
    """colunas.css é o último estilo do index.html; o @import precisa ser a primeira regra dele (senão o navegador ignora)."""
    colunas = (RAIZ / "app_ui" / "pecas" / "colunas.css").read_text(encoding="utf-8")
    primeira = gerador.sem_comentarios(colunas).strip().splitlines()[0]
    assert primeira.startswith('@import url("tema_claro.css")')
    index = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', index)
    assert links[-1] == "/pecas/colunas.css"


def test_toda_regra_so_vale_no_tema_claro():
    """Nenhuma regra do arquivo pode pintar o tema escuro: todas começam pelo tema Claro ou pelo Sistema com o Windows claro."""
    texto = gerador.sem_comentarios(CSS.read_text(encoding="utf-8"))
    for cab, corpo in gerador.blocos(texto):
        pilha = [(cab, corpo)]
        while pilha:
            c, b = pilha.pop()
            if c.startswith("@"):
                pilha.extend(gerador.blocos(b))
                continue
            for sel in gerador.dividir_seletores(c):
                assert sel.startswith((gerador.CLARO, gerador.SISTEMA_CLARO)), sel


def test_sistema_claro_so_dentro_de_prefers_light():
    texto = gerador.sem_comentarios(CSS.read_text(encoding="utf-8"))

    def andar(t, dentro):
        for c, b in gerador.blocos(t):
            if c.startswith("@media"):
                andar(b, dentro or "prefers-color-scheme: light" in c)
            elif not c.startswith("@"):
                if gerador.SISTEMA_CLARO in c:
                    assert dentro, c
    andar(texto, False)


def test_fundo_escuro_vira_claro_e_texto_claro_vira_escuro():
    assert _luz(gerador.clarear("#1f1f1f", "fundo"))[0] > 0.9
    assert _luz(gerador.clarear("#f0f0f0", "texto"))[0] < 0.2
    assert _luz(gerador.clarear("#a8a8a8", "texto"))[0] < 0.4   # texto de apoio: ainda legível no branco
    assert _luz(gerador.clarear("#4a4a4a", "borda"))[0] > 0.6


def test_vidro_escuro_vira_vidro_claro():
    l, a = _luz(gerador.clarear("rgba(8,8,8,.55)", "fundo"))
    assert l > 0.95 and a >= 0.7


def test_cor_de_destaque_mantem_o_tom():
    r, g, b, _ = gerador.ler_cor(gerador.clarear("#6cb8f6", "texto"))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h0 = colorsys.rgb_to_hls(*gerador.ler_cor("#6cb8f6")[:3])[0]
    assert abs(h - h0) < 0.02 and l < 0.35   # o mesmo azul, mais escuro para ler no branco
    assert gerador.clarear("#479ef5", "fundo") == "#479ef5"   # botão azul continua azul
    assert _luz(gerador.clarear("#173b63", "fundo"))[0] > 0.85   # fundo azul-escuro vira azul-claro


def test_sombra_continua_preta_e_mais_fraca():
    r, g, b, a = gerador.ler_cor(gerador.clarear("rgba(0,0,0,.55)", "sombra"))
    assert (r, g, b) == (0, 0, 0) and a < 0.3


def test_variavel_de_destaque_que_e_fundo_e_texto_nao_muda():
    """--verde (#479ef5) pinta o botão Enviar e textos: escurecer deixaria o botão azul-marinho com letra escura."""
    assert gerador.clarear("#479ef5", gerador.tipo_da_prop("--verde")) == "#479ef5"
    assert _luz(gerador.clarear("#e2b64c", gerador.tipo_da_prop("--atencao")))[0] < 0.35   # cor de aviso pinta texto


def test_variacao_de_regra_convertida_entra_junto():
    """'.rb-tri i' (cinza) é convertida; sem '.rb-tri i.f' (verde) junto, a convertida passava por cima e a barrinha ficava cinza."""
    assert gerador.irma(".rb-tri i.f", {".rb-tri i"})
    assert not gerador.irma(".rb-tri", {".rb-tri i"})
    texto = CSS.read_text(encoding="utf-8")
    assert '.rb-tri i.f{' in texto


def test_paleta_clara_de_base_nao_entra():
    """O :root de estilo.css já é a paleta clara antiga: convertê-la escureceria o fundo do tema claro."""
    regras = gerador.regras_do_arquivo((RAIZ / "app_ui" / "estilo.css").read_text(encoding="utf-8"), "estilo.css")
    assert not any(sels == [":root"] for _, sels, _, _ in regras)
