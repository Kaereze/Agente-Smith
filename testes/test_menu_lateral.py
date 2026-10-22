"""Menu da lateral v2 (22/10/2026): só ícones ou com os nomes, e "Quem está neste PC" ao lado da barra."""
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app_ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")


def test_botao_de_mostrar_os_nomes_fica_no_pe_da_barra_e_a_tela_nao_forca_mais_fechado():
    assert HTML.index('id="op-menu"') < HTML.index('id="btn-recolher"') < HTML.index("</aside>")
    assert 'app.classList.add("modo-ol", "menu-fechado")' not in PAINEL
    assert '<div class="app modo-ol menu-fechado">' in HTML            # abre só com os ícones
    assert "painel.menuNomes" in HTML


def test_lista_do_operador_sem_glifo_solto_e_com_iniciais_que_nao_se_repetem():
    bloco = HTML[HTML.index("function desenharOperador"):HTML.index("function desenharOperador") + 2500]
    assert "✓" not in bloco and ">×<" not in bloco
    assert "iniciaisOp(o, opLista)" in bloco and "você, neste PC" in bloco
    assert ".modo-ol .op-menu{position:fixed" in HTML
