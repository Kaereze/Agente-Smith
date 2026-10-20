"""Formulário do hóspede em quadros (usuário, 20/10/2026): os campos saem do próprio texto do e-mail do Emissor
Automático quando o pedido não está na lista do Painel. Roda o JavaScript da tela no Node. Dados inventados."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = (Path(__file__).resolve().parents[1] / "app_ui" / "correio.js").read_text(encoding="utf-8")
TEXTO = ("Enviado por: marina.exemplo@gmail.com <mailto:marina.exemplo@gmail.com>\n\nDados para emissão de Nota Fiscal:\n\n"
         "Campo\tValor\nTermos de aceite\tLi e estou de acordo com os termos acima.\nDocumento Tomador\t52998224725\n"
         "Nome Tomador\tMarina Exemplo Costa\nCEP 01001000\nTelefone para contato\t11999990000\n"
         "Check-in da Hospedagem\t14/10/2026\nInformações necessárias na Nota Fiscal\tValor Diárias Hospedagem\n"
         "Nota Dividida\tNão\n\nEnviado em: Sat Oct 17 2026 08:03:36 GMT-0300 (Brasilia Standard Time)\n")


def _rodar(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    trecho = re.search(r"const ROTULOS_FORM = .*?\nfunction formDoTexto\(texto\) \{.*?\n\}\n", JS, re.S).group(0)
    codigo = trecho + f"\nconsole.log(JSON.stringify({expr}));"
    saida = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_campos_saem_do_texto_do_email():
    f = _rodar(f"formDoTexto({json.dumps(TEXTO)})")
    campos = dict(f["campos"])
    assert campos["Documento Tomador"] == "52998224725" and campos["Nome Tomador"] == "Marina Exemplo Costa"
    assert campos["CEP"] == "01001000"   # sem tab: o rótulo conhecido separa
    assert campos["Informações necessárias na Nota Fiscal"] == "Valor Diárias Hospedagem" and campos["Nota Dividida"] == "Não"
    assert f["email"] == "marina.exemplo@gmail.com" and f["carimbo"] == "Sat Oct 17 2026 08:03:36"


def test_email_comum_continua_texto():
    assert _rodar('formDoTexto("Bom dia, segue o comprovante.\\nCampo Valor")') is None
    assert _rodar("formDoTexto(undefined)") is None


def test_quadros_por_grupo_na_tela():
    assert '["Tomador da nota"' in JS and '["Estadia"' in JS and '["Como quer a nota"' in JS
    assert "formularioHtml(f, e)" in JS and 'class="fg-cp" data-copiar' in JS   # tela 1 do quadro (20/10/2026)


def test_cpf_cnpj_cep_telefone_formatados():
    trecho = re.search(r"function valorDoForm\(rot, v\) \{.*?\n\}\n", JS, re.S).group(0)
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    casos = [["CPF/CNPJ", "12345678000195"], ["CPF do titular", "52998224725"], ["CEP", "01001000"], ["Telefone", "65999990000"],
             ["Datas", "14/10/2026 → 17/10/2026"], ["Nome", "Marina Exemplo Costa"]]
    saida = subprocess.run(["node", "-e", trecho + f"\nconsole.log(JSON.stringify({json.dumps(casos)}.map(([r, v]) => valorDoForm(r, v))));"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    assert json.loads(saida.stdout) == [["12.345.678/0001-95", "CNPJ"], ["529.982.247-25", "CPF"], ["01001-000", ""],
                                        ["(65) 99999-0000", ""], ["14/10/2026 → 17/10/2026", "3 diárias"], ["Marina Exemplo Costa", ""]]
