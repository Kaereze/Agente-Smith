"""Peças únicas (usuário, 20/10/2026: "o mesmo botão em todas as telas; mudou uma vez, muda em todas").
A peça do Filtro existe só em app_ui/pecas/filtro.js; as telas só chamam pecaFiltro/registrarFiltro."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "app_ui"
PECA = (UI / "pecas" / "filtro.js").read_text(encoding="utf-8")


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    # a peça sem o que precisa de navegador (eventos), pra rodar no Node
    trecho = PECA.split("function registrarFiltro")[0]
    saida = subprocess.run(["node", "-e", trecho + f"\nconsole.log(JSON.stringify({expr}));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


OPCOES = """[{ v: "", nome: "Todos os hotéis" }, { v: "LUXOR", nome: "LUXOR", n: 3, grupo: "João" },
  { v: "SOLMAR", nome: "SOLMAR", n: 1200, grupo: "Clara" }, { v: "MAUÁ", nome: "MAUÁ EXPRESS", n: 0, grupo: "Clara" }]"""


def test_fechada_mostra_rotulo_e_valor_sem_menu():
    h = _node(f'pecaFiltro({{ id: "x", rotulo: "Hotel", valor: "", nomePadrao: "Todos", opcoes: {OPCOES} }})')
    assert "Hotel: <b>Todos</b>" in h and "ol-filtro-menu" not in h and "ol-filtro-x" not in h
    assert 'class="ol-filtro-bt "' in h   # sem filtro: sem o azul


def test_ativa_tem_o_azul_e_o_x_que_volta_ao_padrao():
    h = _node(f'pecaFiltro({{ id: "x", rotulo: "Hotel", valor: "LUXOR", nomePadrao: "Todos", opcoes: {OPCOES} }})')
    assert "Hotel: <b>LUXOR</b>" in h and "ol-filtro-bt on" in h
    assert 'class="ol-filtro-x" data-pf-escolher="x" data-v=""' in h


def test_aberta_com_grupos_contagem_e_busca_sem_acento():
    h = _node(f'(PF.aberto = "x", pecaFiltro({{ id: "x", rotulo: "Hotel", valor: "", busca: true, opcoes: {OPCOES} }}))')
    assert 'class="pf-grupo">João' in h and 'class="pf-grupo">Clara' in h and "<em>1.200</em>" in h and 'data-pf-busca="x"' in h
    filtrado = _node(f'(PF.aberto = "x", PF.busca.x = "maua", pecaFiltro({{ id: "x", rotulo: "Hotel", busca: true, opcoes: {OPCOES} }}))')
    assert "MAUÁ EXPRESS" in filtrado and "LUXOR" not in filtrado and "João" not in filtrado
    vazio = _node(f'(PF.aberto = "x", PF.busca.x = "zzz", pecaFiltro({{ id: "x", rotulo: "Hotel", busca: true, opcoes: {OPCOES} }}))')
    assert "Nada com esse nome" in vazio


def test_separador_bolinha_e_texto_no_lugar_da_contagem():
    h = _node('(PF.aberto = "p", pecaFiltro({ id: "p", rotulo: "PC", opcoes: [{ v: "", nome: "Todos os PCs", n: "3 ligados" },'
              ' { v: "A", nome: "Clara", n: "PC-A", bolinha: "on", sep: true }, { v: "B", nome: "Bernardo", n: "desligado", bolinha: "off" }] }))')
    assert "<hr>" in h and '<i class="pc-bol on"' in h and '<i class="pc-bol "' in h and "<em>3 ligados</em>" in h


def test_o_menu_so_e_montado_pela_peca():
    """A garantia da peça única: nenhum outro arquivo da tela monta o menu do filtro por conta própria."""
    for arq in [*UI.glob("*.js"), UI / "index.html"]:
        texto = arq.read_text(encoding="utf-8")
        assert 'class="ol-filtro-menu' not in texto, f"{arq.name} monta o menu do filtro sozinho: use pecaFiltro"
        assert 'class="ol-filtro-bt' not in texto, f"{arq.name} monta o botão do filtro sozinho: use pecaFiltro"
    todo = "".join(a.read_text(encoding="utf-8") for a in [*UI.glob("*.js"), UI / "index.html"])
    for antigo in ("popAberto", "desenharPop", "function pilula", 'id="pop"', "nfFiltroAberto", "cx.filtroAberto", "at.pcAberto"):
        assert antigo not in todo, f"sobrou código do filtro antigo: {antigo}"
    for id_ in ("cx-filtro", "cx-hotel", "nf-situacao", "nf-hotel"):
        assert f'registrarFiltro("{id_}"' in todo, f"o filtro {id_} não usa a peça"


def test_a_peca_carrega_antes_das_telas_e_o_servidor_entrega():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert html.index('<script src="/pecas/filtro.js"></script>') < html.index("<script>\nconst TOKEN") < html.index('<script src="/correio.js">')
    import app_servidor
    assert app_servidor.ESTATICOS["/pecas/filtro.js"][0] == "pecas/filtro.js"
    assert re.search(r"pecas", Path(app_servidor.__file__).read_text(encoding="utf-8").split("def _marca_pagina")[1][:400])
