"""Peça única das etiquetas (usuário, 21/10/2026): 5 situações + 5 alertas, regras num lugar só (pecas/etiqueta.js).
Decisões do João: responder NÃO vira "NF enviada"; "diz que falta nota" é o alerta "Diz que não recebeu"."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "app_ui"
PECA = (UI / "pecas" / "etiqueta.js").read_text(encoding="utf-8")


def _node(expr, stubs=""):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", stubs + PECA + f"\nconsole.log(JSON.stringify({expr}));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


STUBS = ("const faltaDados = s => s.falta || []; const motivoUrgente = s => s.urg || '';"
         " let PED = null; const pedidoDoEmail = () => PED;\n")


def test_situacao_do_pedido_segue_as_regras():
    casos = _node("""[
      situacaoDoPedido({ situacao: "na_fila" }), situacaoDoPedido({ situacao: "aguardando_envio" }),
      situacaoDoPedido({ situacao: "tratativa", falta: ["CPF/CNPJ"] }), situacaoDoPedido({ situacao: "concluida", envio_pendente: true }),
      situacaoDoPedido({ situacao: "concluida" }), situacaoDoPedido({ situacao: "nf_parcial" })]""", STUBS)
    assert casos == ["sem_nf", "sem_nf", "falta", "pronta", "enviada", "sem_nf"]


def test_etiquetas_do_pedido_com_alertas():
    h = _node('etiquetasDoPedido({ situacao: "na_fila", falta: ["CPF/CNPJ", "nome"], urg: "Vence em 4 h", dividida: true, falta_nota: "não chegou", alerta_doc: [] })', STUBS)
    assert "Falta dado: CPF/CNPJ +1" in h and "s-falta" in h and "a-urg" in h and "Vence em 4 h" in h and "a-div" in h and "a-nrec" in h
    rep = _node('etiquetasDoPedido({ situacao: "na_fila", urg: "Cobrou de novo" })', STUBS)
    assert "a-dup" in rep and "Pediu de novo" in rep and "a-urg" not in rep
    env = _node('etiquetasDoPedido({ situacao: "concluida", nfs: ["879"] })', STUBS)
    assert "NF enviada · 879" in env and "s-enviada" in env


def test_etiquetas_do_email():
    corr = _node('etiquetasDoEmail({ classes: ["corrigir"], urgente: true, motivo_urgencia: "Pedido de correção/cancelamento da NF" })', STUBS)
    assert "s-corr" in corr and "a-urg" not in corr   # correção já é a situação; não repete como urgente
    atraso = _node('etiquetasDoEmail({ classes: [], urgente: true, motivo_urgencia: "9 dias sem resposta", quartos: 2 })', STUBS)
    assert "Sem resposta há 9 dias" in atraso and "s-semnf" in atraso and "a-div" in atraso
    pronta = _node('etiquetasDoEmail({ classes: [], notas: [{ nf: "1212", nome: "NF 1212.pdf" }] })', STUBS)
    assert "NF pronta, falta enviar · 1212" in pronta
    ligado = _node('(PED = { situacao: "na_fila", falta: ["CPF/CNPJ"], urg: "Vence em 2 h" }, etiquetasDoEmail({ classes: [] }))', STUBS)
    assert "Falta dado: CPF/CNPJ" in ligado and "Vence em 2 h" not in ligado   # alerta do pedido não duplica no e-mail


def test_as_telas_so_usam_a_peca():
    todo = "".join(a.read_text(encoding="utf-8") for a in [*UI.glob("*.js"), UI / "index.html"])
    for antigo in ('class="tg t-urg', 'class="tg t-falta', 'class="tg t-div', "pilula p-${", "NOMES[s.situacao]", "NOMES[f.situacao]", "NOMES[o.situacao]"):
        assert antigo not in todo, f"sobrou etiqueta montada fora da peça: {antigo}"
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/pecas/etiqueta.css">' in html and '<script src="/pecas/etiqueta.js"></script>' in html
    assert html.index('<script src="/pecas/etiqueta.js"></script>') < html.index('<script src="/correio.js">')
