"""Assunto do e-mail pelo nome do PDF da NF (João, 07/11/2026): anexou a nota, o assunto vira o nome do arquivo."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAINEL = (Path(__file__).resolve().parents[1] / "app_ui" / "painel.js").read_text(encoding="utf-8")
TRECHO = PAINEL[PAINEL.index("function assuntoDoArquivo"):PAINEL.index("// Ação longa (27/10/2026)")]


def _rodar(passos):
    """passos: JavaScript que usa `anexar(nome)`, `tirar()`, `digitar(texto)` e devolve o assunto com `assunto()`."""
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    cabeca = """
    let valor = "Re: Dados para emissão da NF";
    const campo = { get value() { return valor; }, set value(v) { valor = v; } };
    const $ = () => campo;
    let envNF = { anexos: [], assuntoManual: false, assuntoAntes: null, o: { nome: "Ana Lima" } };
    const anexar = nome => { envNF.anexos.push({ nome }); assuntoComAnexos(); };
    const tirar = () => { envNF.anexos.pop(); assuntoComAnexos(); };
    const digitar = t => { valor = t; envNF.assuntoManual = !!t.trim(); };
    const assunto = () => valor;
    """
    saida = subprocess.run(["node", "-e", cabeca + TRECHO + f"\nconsole.log(JSON.stringify({passos}));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_anexou_o_pdf_da_nf_o_assunto_vira_o_nome_do_arquivo():
    assert _rodar('(anexar("NF 1234 - ANA LIMA - 5678.pdf"), assunto())') == "NF 1234 - ANA LIMA - 5678"


def test_arquivo_fora_do_padrao_vira_nf_numero_e_nome_do_hospede():
    assert _rodar('(anexar("nota 987.pdf"), assunto())') == "NF 987 - ANA LIMA"


def test_prefere_o_pdf_quando_ha_mais_de_um_anexo():
    assert _rodar('(anexar("foto.png"), anexar("NF 55 - ANA LIMA - 9.pdf"), assunto())') == "NF 55 - ANA LIMA - 9"


def test_tirou_o_anexo_volta_o_assunto_de_antes():
    assert _rodar('(anexar("NF 1 - ANA LIMA - 2.pdf"), tirar(), assunto())') == "Re: Dados para emissão da NF"


def test_assunto_digitado_a_mao_nao_e_trocado():
    assert _rodar('(digitar("Meu assunto"), anexar("NF 1 - ANA LIMA - 2.pdf"), assunto())') == "Meu assunto"


def test_apagou_o_assunto_o_painel_volta_a_preencher():
    assert _rodar('(digitar("x"), digitar(""), anexar("NF 1 - ANA LIMA - 2.pdf"), assunto())') == "NF 1 - ANA LIMA - 2"


def test_a_janela_usa_a_funcao_e_nao_ha_mais_assunto_auto_antigo():
    assert "assuntoAuto" not in PAINEL and PAINEL.count("assuntoComAnexos()") >= 2
    assert re.search(r"addEventListener\(\"input\", ev => \{ if \(ev\.isTrusted\)", PAINEL)
