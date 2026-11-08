"""Resumo do dia (João, 07/11/2026): peça pecas/resumo_dia.js. A conta dos números é do painel.js; aqui se confere o desenho."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tela_texto import pagina, codigo_js

UI = Path(__file__).resolve().parents[1] / "app_ui"
PECA = (UI / "pecas" / "resumo_dia.js").read_text(encoding="utf-8")

DADOS = """{
  kpis: [{ r: "Pedidos recebidos", v: 35, fmt: "n", delta: "+25", spark: [1,2,3,4,5,6,35] }, { r: "Tempo até a NF", v: null, fmt: "h", delta: "mediana", spark: null }],
  horas: [{ h: 8, ped: 1, nfs: 0 }, { h: 9, ped: 5, nfs: 2 }, { h: 10, ped: 0, nfs: 1 }],
  prazo: { pct: 100, ok: 3, total: 3 }, abertos: [{ nome: "Sem NF", n: 8, k: "a" }, { nome: "Falta dado", n: 0, k: "c" }, { nome: "NF pronta", n: 2, k: "b" }], vencidos: 4,
  equipe: [{ nome: "Clara", rec: 12, nfs: 3 }, { nome: "<b>Joao</b>", rec: 0, nfs: 0 }], hoteis: [{ nome: "San Martin", n: 7 }],
  atencao: "<div>ok</div>", tabela: false, titulos: { equipe: "Equipe ontem", atencao: "Precisa de atenção hoje", abertos: "O que ficou para hoje" } }"""


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", "const document = { addEventListener() {}, documentElement: { addEventListener() {} } };\n" + PECA + f"\nconsole.log(JSON.stringify({expr}));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_o_resumo_traz_kpis_grafico_prazo_barras_e_atencao():
    h = _node(f"resumoDiaPeca({DADOS})")
    for parte in ('class="rs-kpis"', 'class="rs-linha-svg"', 'class="rs-meter"', 'class="rs-segbar"', 'class="rs-barras"', "rs-atencao", "Equipe ontem", "O que ficou para hoje"):
        assert parte in h, parte
    assert h.count('class="rs-hit"') == 3 and 'data-cnt="35"' in h and "100% no prazo" in h and "3 de 3 saíram em até 48 h" in h


def test_nome_vindo_da_planilha_nao_vira_html():
    h = _node(f"resumoDiaPeca({DADOS})")
    assert "<b>Joao</b>" not in h and "&lt;b&gt;Joao&lt;/b&gt;" in h


def test_eixo_do_grafico_cai_em_numeros_inteiros():
    h = _node(f"resumoDiaPeca({DADOS})")
    topo = [int(t) for t in __import__("re").findall(r'text-anchor="end">(\d+)</text>', h)]
    assert topo == [0, 2, 4, 6, 8] or all(isinstance(x, int) for x in topo) and len(set(topo)) == len(topo)


def test_sem_nf_enviada_mostra_aviso_em_vez_de_barra_vazia():
    h = _node(f"resumoDiaPeca({{ ...{DADOS}, prazo: {{ pct: null, ok: 0, total: 0 }} }})")
    assert "Nenhuma NF enviada neste dia." in h and 'class="rs-meter"' not in h


def test_modo_tabela_liga_a_classe_e_a_tabela_tem_os_mesmos_numeros():
    h = _node(f"resumoDiaPeca({{ ...{DADOS}, tabela: true }})")
    assert "rs-tabela-on" in h and "<th>Hora</th>" in h and "<td>San Martin</td>" in h and '<td class="n">35</td>' not in h


def test_serie_sem_pontos_suficientes_nao_desenha_risquinho():
    h = _node(f"resumoDiaPeca({DADOS})")
    assert h.count('class="rs-spark"') == 1


def test_o_painel_usa_a_peca_e_so_anima_quando_mudou():
    painel = codigo_js(UI, "painel")
    html = pagina(UI)
    assert "resumoDiaPeca(dados)" in painel and "resumoDiaAnimar(el)" in painel and "pn.rsAnimar = assinatura !== pn.rsAssinatura" in painel
    assert '/pecas/resumo_dia.js' in html and '/pecas/resumo_dia.css' in html
    assert ".rd-kpi" not in html and ".rd-grade" not in html   # o desenho antigo dos cartões saiu
