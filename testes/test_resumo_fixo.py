"""Resumo fixo do hóspede (usuário, 21/10/2026: desenho Pr1/Pr2 do quadro): a faixa parada no topo do e-mail substitui a
ficha de 3 faixas; a ficha completa abre a mesma tabela do formulário (peça formularioHtml)."""
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "app_ui"
JS = (UI / "correio.js").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")


def test_a_faixa_entra_no_topo_e_a_ficha_antiga_sai():
    assert '<div class="ol-leitura${entra}">${enviado ? "" : resumoFixoHtml(e) + avisoRepetidoHtml(e)}<div class="ol-cab">' in JS
    assert "fichaPedidoOl" not in JS   # a ficha de 3 faixas saiu (os dados estão na faixa e na ficha completa)
    assert "Prazo de resposta:" not in JS   # o prazo agora fica na faixa


def test_a_faixa_usa_as_pecas_unicas():
    corpo = JS.split("function resumoFixoHtml(e) {")[1].split("\n}\n")[0]
    assert "etiquetasDoEmail(e)" in corpo and "formularioHtml(r.dados, e)" in corpo and 'data-cx-faixa="nf"' in corpo
    assert "data-pedir-dados" in corpo and "data-abrir-ficha" in corpo and "data-resumo-ficha" in corpo


def test_a_faixa_fica_parada_e_lembra_a_ficha_aberta():
    assert "#v-correio.ol .ol-resumo{position:sticky;top:0;" in HTML
    assert 'localStorage.getItem("painel.fichaAberta")' in JS and 'localStorage.setItem("painel.fichaAberta"' in JS
