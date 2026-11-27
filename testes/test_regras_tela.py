"""As regras do pedido de NF na tela em React (app_react/src/dados/formulario.js), rodadas no Node: o que falta para emitir
(nome, CPF/CNPJ com os dígitos conferindo, CEP; telefone só na mensagem), o texto da emissão (nada inventado), o assunto pelo
nome do PDF da NF, a leitura do formulário do Emissor e as etiquetas. Mesmos casos dos testes da tela de antes (regras_nf.js,
hospede.js, painel_enviar_nf.js), que saiu em 27/11/2026. Sem Node, os testes são pulados."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REGRAS = (Path(__file__).resolve().parents[1] / "app_react" / "src" / "dados" / "formulario.js").as_uri()


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    codigo =f"import * as f from '{REGRAS}';\nconsole.log(JSON.stringify((({{ {', '.join(NOMES)} }}) => {expr})(f)));"
    saida = subprocess.run(["node", "--input-type=module", "-e", codigo], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


NOMES = ["cpfValido", "cnpjValido", "cepValido", "faltaDados", "faltaExtras", "textoEmissao", "assuntoDoArquivo", "formDoTexto", "valorDoForm",
         "etiquetasDoEmail", "situacaoDoPedido", "etapasDoPedido", "modeloPedirFalta", "dadosDoModelo", "prazoInfo", "seloDoDocumento"]
COMPLETO = '[["Nome Tomador","Ana Lima"],["Documento Tomador","529.982.247-25"],["CEP","01310-100"],["Telefone para contato","(11) 91234-5678"]]'


def test_cpf_e_cnpj_conferem_os_digitos():
    r = _node('[cpfValido("529.982.247-25"), cpfValido("529.982.247-24"), cpfValido("111.111.111-11"), cnpjValido("11.222.333/0001-81"), cnpjValido("11.222.333/0001-82"), cepValido("01310-100"), cepValido("0131")]')
    assert r == [True, False, False, True, False, True, False]


def test_o_que_falta_para_emitir():
    assert _node(f'faltaDados({{ campos: {COMPLETO} }})') == []
    assert _node('faltaDados({ campos: [["Nome Tomador",""],["Documento Tomador",""],["CEP",""]] })') == ["nome", "CPF/CNPJ", "CEP"]
    assert _node('faltaDados({ campos: [["Nome Tomador","Ana"],["Documento Tomador","529.982.247-24"],["CEP","123"]] })') == ["CPF/CNPJ inválido", "CEP inválido"]
    assert _node('faltaDados({ campos: [["Nome Tomador","Empresa"],["Documento Tomador","11.222.333/0001-81"],["CEP","01310100"]] })') == []
    assert _node('faltaDados({ situacao: "concluida", campos: [] })') == []   # concluída nunca falta dado


def test_telefone_vazio_so_entra_na_mensagem():
    campos = '[["Nome Tomador","Ana"],["Documento Tomador","529.982.247-25"],["CEP","01310-100"],["Telefone para contato",""]]'
    assert _node(f'faltaDados({{ campos: {campos} }})') == []
    assert _node(f'faltaExtras({{ campos: {campos} }})') == ["telefone"]
    assert _node('faltaExtras({ campos: [["Nome Tomador","Ana"]] })') == []   # só se o formulário tem o campo
    msg = _node('modeloPedirFalta(["CPF/CNPJ inválido", "telefone"])')
    assert "não confere" in msg and "Telefone para contato:" in msg


def test_texto_da_emissao_nao_inventa_nada():
    base = '[["Check-in da Hospedagem","20/11/2026"],["Check-out da Hospedagem","23/11/2026"],["Nome do Titular da Reserva","Henrique Barbosa"]]'
    linhas = _node(f'textoEmissao({{ campos: {base} }}).split("\\n")')
    assert linhas == ["DATA DE CHECK-IN : 20/11/2026", "DATA DE CHECK-OUT : 23/11/2026", "QUANTIDADE DE DIÁRIAS : 3", "VALOR DA DIÁRIA :", "", "VALOR TOTAL :", "Henrique Barbosa"]
    com = _node('textoEmissao({ campos: [["Check-in da Hospedagem","20/11/26"],["Check-out da Hospedagem","2026-11-21"],["Nome Tomador","Ana"],["Valor da Nota","R$ 1.840,00"],["Observação","Estada 2202"]] }).split("\\n")')
    assert com[0] == "DATA DE CHECK-IN : 20/11/2026" and com[2] == "QUANTIDADE DE DIÁRIAS : 1" and com[5] == "VALOR TOTAL : R$ 1.840,00" and com[6] == "Ana - ESTADA 2202"
    errado = _node('textoEmissao({ campos: [["Check-in da Hospedagem","05/11/2026"],["Check-out da Hospedagem","03/11/2026"],["Nome Tomador","Fulano"]] }).split("\\n")')
    assert errado[2] == "QUANTIDADE DE DIÁRIAS : "   # check-out antes do check-in: nada de número
    ilegivel = _node('textoEmissao({ campos: [["Check-in da Hospedagem","semana que vem"],["Nome Tomador","Fulano"]] }).split("\\n")')
    assert ilegivel[0] == "DATA DE CHECK-IN : semana que vem" and ilegivel[1] == "DATA DE CHECK-OUT : " and ilegivel[2] == "QUANTIDADE DE DIÁRIAS : "


def test_assunto_pelo_nome_do_pdf_da_nf():
    assert _node('assuntoDoArquivo("NF 1234 - ANA LIMA - 5678.pdf", "Ana Lima")') == "NF 1234 - ANA LIMA - 5678"
    assert _node('assuntoDoArquivo("nota 987.pdf", "Ana Lima")') == "NF 987 - ANA LIMA"
    assert _node('assuntoDoArquivo("scan.pdf", "Ana Lima")') == "NF - ANA LIMA"


def test_formulario_do_emissor_sai_do_texto_do_email():
    texto = "Dados para emissão de Nota Fiscal\\nEnviado por: ana@exemplo.invalid\\nCampo\\tValor\\nDocumento Tomador\\t529.982.247-25\\nNome Tomador Ana Lima\\nEnviado em: 27/11/2026 05:11:07 GMT-3"
    f = _node(f'formDoTexto("{texto}")')
    assert f["email"] == "ana@exemplo.invalid" and f["carimbo"] == "27/11/2026 05:11:07"
    assert f["campos"] == [["Documento Tomador", "529.982.247-25"], ["Nome Tomador", "Ana Lima"]]   # sem tab: acha pelo rótulo conhecido
    assert _node('formDoTexto("Bom dia, segue o pedido")') is None


def test_valores_formatados_e_selo_do_documento():
    assert _node('[valorDoForm("CPF/CNPJ", "52998224725"), valorDoForm("CPF/CNPJ", "11222333000181"), valorDoForm("CEP", "01310100"), valorDoForm("Telefone", "11912345678"), valorDoForm("Datas", "20/11/2026 → 23/11/2026")]') == [
        ["529.982.247-25", "CPF"], ["11.222.333/0001-81", "CNPJ"], ["01310-100", ""], ["(11) 91234-5678", ""], ["20/11/2026 → 23/11/2026", "3 diárias"]]
    assert _node('[seloDoDocumento("529.982.247-24"), seloDoDocumento("11.222.333/0001-81"), seloDoDocumento("")]') == [["CPF com dígito errado", False], ["CNPJ válido", True], None]


def test_etiquetas_e_etapas_do_pedido():
    fila = '[{ chave: "k1", situacao: "na_fila", campos: [["Nome Tomador",""],["Documento Tomador","529.982.247-25"],["CEP","01310100"]] }]'
    t = _node(f'etiquetasDoEmail({{ solicitacao: {{ chave: "k1" }}, urgente: true, motivo_urgencia: "9 dias sem resposta", quartos: 2 }}, {fila}).map(x => x.texto)')
    assert t == ["Falta dado: nome", "Sem resposta há 9 dias", "÷ Nota dividida"]
    assert _node('etiquetasDoEmail({ classes: ["corrigir"], urgente: true }, []).map(x => x.texto)') == ["Correção"]   # correção não soma o "Urgente"
    e = _node('etapasDoPedido({ falta: ["CEP"], temPedido: true })')
    assert e["principal"] == {"texto": "Pedir o que falta", "acao": "pedir"} and [p["nome"] for p in e["passos"]] == ["Recebido", "Dados completos"]
    assert _node('etapasDoPedido({ falta: [], temPedido: true }).principal.acao') == "nf"


def test_prazo_conta_o_que_falta():
    assert _node('prazoInfo({ vence: new Date(Date.now() + 30 * 3600e3).toISOString(), horas: 48 }).nivel') == "ok"
    assert _node('prazoInfo({ vence: new Date(Date.now() + 10 * 3600e3).toISOString(), horas: 48 }).nivel') == "perto"   # metade do prazo
    assert _node('prazoInfo({ vence: new Date(Date.now() - 2 * 3600e3).toISOString(), horas: 24 }).texto') == "venceu há 2 h"
    assert _node("prazoInfo(null)") is None
