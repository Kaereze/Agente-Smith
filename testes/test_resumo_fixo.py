"""Etapas do pedido (27/10/2026, opção C aprovada pelo João): a ficha única no topo do e-mail (pecas/etapas.js) substitui o
resumo antigo e as caixas empilhadas (NF já enviada, NF enviada, histórico do hóspede). A ficha completa continua abrindo a
mesma tabela do formulário (peça formularioHtml)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "app_ui"
JS = (UI / "correio.js").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")
PECA = (UI / "pecas" / "etapas.js").read_text(encoding="utf-8")
CSS = (UI / "pecas" / "etapas.css").read_text(encoding="utf-8")


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", PECA + "\nconsole.log(JSON.stringify(" + expr + "));"], capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_a_ficha_unica_entra_no_topo_e_as_caixas_antigas_saem():
    assert "resumoFixoHtml(e, !!entra)" in JS and "etapasTelaHtml(" in JS
    leitura = JS.split("function desenharLeituraCorreio")[1].split("function carregarCobre")[0]
    assert "avisoNfJaEnviada(" not in leitura and "nfCobreHtml(" not in leitura and "historicoHtml(" not in leitura
    assert '<link rel="stylesheet" href="/pecas/etapas.css">' in HTML and '<script src="/pecas/etapas.js"></script>' in HTML
    assert HTML.index("/pecas/etapas.js") < HTML.index("const TOKEN")


def test_a_ficha_continua_com_os_botoes_e_a_ficha_completa():
    assert "data-pedir-dados" in PECA and "data-abrir-ficha" in PECA and "data-nf-concluir" in PECA and 'data-cx-faixa="nf"' in PECA
    assert "data-resumo-ficha" in PECA and 'localStorage.setItem("painel.fichaAberta"' in JS


def test_paleta_sem_verde():
    assert "#2e7d57" not in CSS and "--c-azul:#479ef5" in CSS and "--c-am:#f0c46a" in CSS


BASE = "{ hora: '21:17', falta: [], tom: 'Rota Sul', doc: '27.598.834/0001-20', datas: '23/10 → 24/10/2026', diarias: '1 diária', valor: 'R$ 190,00', pede: 'Hospedagem', temPedido: true"


def test_situacao_e_botao_principal_mudam_com_o_pedido():
    casos = _node(f"""[
      etapasModelo({BASE} , falta: ['CPF/CNPJ'] }}), etapasModelo({BASE} }}), etapasModelo({BASE}, notas: [{{ nf: '1602' }}] }}),
      etapasModelo({BASE}, nfsEnviadas: [{{ nf: '1552', quando: '27/10 17:45' }}] }}), etapasModelo({BASE}, situacaoPedido: 'enviada' }})
    ].map(m => [m.estado, m.principal.texto, m.principal.cls, m.passos.map(p => p.cls)])""")
    assert casos[0][:3] == ["falta", "Pedir o que falta", "p"] and casos[0][3][1] == "atual"
    assert casos[1][:3] == ["completo", "Enviar NF", ""] and casos[1][3] == ["feita", "feita", "atual azul", ""]
    assert casos[2][:3] == ["pronta", "Enviar NF", "p"]
    assert casos[3][:3] == ["enviada", "Concluir", "p"] and casos[3][3] == ["feita"] * 4
    assert casos[4][0] == "enviada"


def test_itens_marcam_o_que_falta_e_avisos_da_nf_enviada():
    m = _node(f"etapasModelo({BASE}, doc: '', falta: ['CPF/CNPJ'] }})")
    assert [i["tipo"] for i in m["itens"]][:2] == ["ok", "at"] and m["itens"][1]["val"] == "CPF ou CNPJ"
    nova = _node(f"etapasModelo({BASE}, nfsEnviadas: [{{ nf: '1552' }}], cobre: {{ cobre: false, pede_nova: true, motivos: ['pede estacionamento'] }} }})")
    assert any(i["tipo"] == "at" and "Pede nova nota: pede estacionamento" in i["val"] for i in nova["itens"]) and nova["passos"][3]["cls"] == "feita atencao"
    sem = _node(f"etapasModelo({BASE}, nfsEnviadas: [{{ nf: '1552' }}], cobre: {{ avisos_envio: ['1552'] }} }})")
    assert any(i["tipo"] == "at" and "não achei o envio da NF 1552" in i["val"] for i in sem["itens"])
    texto = _node("etapasModelo({ hora: '10:00', falta: [], semFormulario: true, temPedido: false })")
    assert texto["itens"] == [] and texto["principal"]["acao"] == "nf" and texto["secundario"] is None
