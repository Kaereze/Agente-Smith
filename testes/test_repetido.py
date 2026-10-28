"""Aviso de pedido repetido no e-mail (usuário, 21/10/2026: "1 · Mostrar no e-mail"): só tela; a junção automática do
robô (hospedes.marcar) continua igual e nada é gravado. Dados inventados."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "app_ui"
JS = (UI / "correio.js").read_text(encoding="utf-8")


def test_o_aviso_entra_embaixo_do_resumo_e_nao_grava_nada():
    assert 'resumoFixoHtml(e, !!entra)}${avisoRepetidoHtml(e)}' in JS
    corpo = JS.split("function avisoRepetidoHtml(e) {")[1].split("\n}\n")[0]
    assert "data-ver-pedido" in corpo and "data-repetido-comparar" in corpo
    assert "api(" not in corpo   # só tela


def test_comparacao_marca_o_que_e_diferente():
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    trecho = re.search(r"function outroDoRepetido\(s\) \{.*?\nfunction avisoRepetidoHtml", JS, re.S).group(0).rsplit("function avisoRepetidoHtml", 1)[0]
    stubs = ("const campoDoPedido = (s, ...r) => { const c = (s.campos || []).find(([k]) => r.some(x => x.test(k.toLowerCase()))); return c ? c[1] : ''; };"
             " const nomeSituacao = s => s.situacao; const PEDS = {}; const acharPedido = k => PEDS[k];"
             " const valorDoForm = (r, v) => [v.length === 11 ? v.replace(/(\\d{3})(\\d{3})(\\d{3})(\\d{2})/, '$1.$2.$3-$4') : v, 'CPF'];\n")
    a = {"chave": "A", "repetido_de": "B", "hotel": "CENTER PREMIUM", "data": "2026-10-21", "situacao": "na_fila",
         "campos": [["nome do titular", "Marina Exemplo Costa"], ["documento tomador", "52998224725"], ["check-in", "14/10/2026"], ["check-out", "17/10/2026"]]}
    b = {**a, "chave": "B", "repetido_de": "", "data": "2026-10-19", "situacao": "concluida",
         "campos": [*a["campos"], ["nome tomador", "COOPERATIVA EXEMPLO"]]}
    expr = f"(PEDS.B = {json.dumps(b)}, {{ outro: outroDoRepetido({json.dumps(a)}).chave, linhas: linhasComparacao({json.dumps(a)}, PEDS.B) }})"
    saida = subprocess.run(["node", "-e", stubs + trecho + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    r = json.loads(saida.stdout)
    assert r["outro"] == "B"
    dif = {linha[0]: linha[3] for linha in r["linhas"]}
    assert r["linhas"][1][1] == "529.982.247-25"   # CPF/CNPJ formatado como na ficha
    assert dif["Nota em"] is True and dif["CPF/CNPJ"] is False and dif["Datas"] is False and dif["Situação"] is False
