"""A aba "Notas fiscais" está reservada para a emissão automática (João, 07/11/2026): nada pode mandar para ela (09/11/2026).
Só o item do menu lateral (que mostra "em construção") continua apontando para lá."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
UI = RAIZ / "app_ui"


def _fontes():
    return {p.name: p.read_text(encoding="utf-8") for p in list(UI.glob("*.js")) + list((UI / "pecas").glob("*.js"))}


def test_nenhum_codigo_manda_para_a_aba_notas_fiscais():
    for nome, texto in _fontes().items():
        if nome == "telas_notas.js":   # a própria tela guardada: irPraCaixa é de dentro dela, nunca chamado de fora
            continue
        assert 'trocarVista("fila")' not in texto and "trocarVista('fila')" not in texto, nome
        assert 'data-vista="fila"' not in texto, nome


def test_abrir_notas_agora_leva_para_a_caixa_de_entrada():
    fonte = _fontes()["telas_notas.js"]
    ini = fonte.index("function abrirNotas(")
    corpo = fonte[ini:fonte.index("\n}\n", ini)]
    assert 'trocarVista("correio")' in corpo and 'trocarVista("fila")' not in corpo


def test_endereco_desconhecido_nao_cai_na_aba_reservada():
    assert 'if (!TITULOS[v]) v = "visao";' in _fontes()["painel.js"]


def test_so_o_menu_lateral_aponta_para_a_aba_reservada():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert html.count('data-vista="fila"') == 1 and 'aria-label="Notas fiscais" data-vista="fila"' in html


def test_so_formulario_abre_a_ficha_e_a_seta_nao():
    fonte = _fontes()
    assert "emailEhFormulario(e)" in fonte["correio_leitura.js"] and "abrirEmail(prox.dataset.id, true)" in fonte["correio_acoes.js"]
    assert 'e.pasta !== "enviado" && (e.classes || []).includes("formulario")' in fonte["hospede.js"]   # o que enviamos nunca vira ficha
