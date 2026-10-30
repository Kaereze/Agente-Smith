"""Regras do que falta para emitir a NF (João, 30/10/2026): pecas/regras_nf.js.
Principal: nome, CPF/CNPJ com dígitos conferindo e CEP. Telefone e número do endereço só entram na mensagem."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "app_ui"
PECA = (UI / "pecas" / "regras_nf.js").read_text(encoding="utf-8")


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", PECA + f"\nconsole.log(JSON.stringify({expr}));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


COMPLETO = '[["Nome Tomador","Ana Lima"],["Documento Tomador","529.982.247-25"],["CEP","01310-100"],["Telefone para contato","(11) 91234-5678"]]'


def test_cpf_e_cnpj_conferem_os_digitos():
    r = _node('[cpfValido("529.982.247-25"), cpfValido("529.982.247-24"), cpfValido("111.111.111-11"), cnpjValido("11.222.333/0001-81"), cnpjValido("11.222.333/0001-82"), cepValido("01310-100"), cepValido("0131")]')
    assert r == [True, False, False, True, False, True, False]


def test_pedido_completo_nao_falta_nada():
    assert _node(f'faltaDados({{ campos: {COMPLETO} }})') == []


def test_sem_nome_cpf_e_cep_falta_os_tres():
    assert _node('faltaDados({ campos: [["Nome Tomador",""],["Documento Tomador",""],["CEP",""]] })') == ["nome", "CPF/CNPJ", "CEP"]


def test_digito_errado_pede_de_novo_em_vez_de_passar():
    r = _node('faltaDados({ campos: [["Nome Tomador","Ana"],["Documento Tomador","529.982.247-24"],["CEP","123"]] })')
    assert r == ["CPF/CNPJ inválido", "CEP inválido"]


def test_cnpj_de_empresa_vale():
    assert _node('faltaDados({ campos: [["Nome Tomador","Empresa"],["Documento Tomador","11.222.333/0001-81"],["CEP","01310100"]] })') == []


def test_concluida_nunca_falta_dado():
    assert _node('faltaDados({ situacao: "concluida", campos: [] })') == []


def test_o_que_quer_na_nota_nao_e_mais_obrigatorio():
    assert _node(f'faltaDados({{ campos: {COMPLETO} }}).includes("o que quer na nota")') is False


def test_telefone_vazio_so_entra_nos_extras_e_nunca_vira_falta_dado():
    campos = '[["Nome Tomador","Ana"],["Documento Tomador","529.982.247-25"],["CEP","01310-100"],["Telefone para contato",""]]'
    assert _node(f'faltaDados({{ campos: {campos} }})') == []
    assert _node(f'faltaExtras({{ campos: {campos} }})') == ["telefone"]
    assert _node(f'faltaExtras({{ campos: {COMPLETO} }})') == []


def test_extra_so_vale_se_o_formulario_tem_o_campo():
    assert _node('faltaExtras({ campos: [["Nome Tomador","Ana"]] })') == []


def test_tela_usa_a_peca_e_o_marcar_tratativa_saiu():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '/pecas/regras_nf.js' in html and "function faltaDados" not in html
    assert "[...faltaDados(s), ...faltaExtras(s)]" in html
    assert 'texto: "Marcar tratativa"' not in (UI / "pecas" / "etapas.js").read_text(encoding="utf-8")   # o botão saiu
    msg = (UI / "painel.js").read_text(encoding="utf-8")
    assert '"CEP"' in msg and '"CPF/CNPJ inválido"' in msg and "nf-msg" in msg   # a mensagem sai preparada no campo editável
