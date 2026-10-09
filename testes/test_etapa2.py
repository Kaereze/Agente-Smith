"""Etapa 2 (09/10/2026): prazo por tipo, hóspede único, pedido repetido, CPF/CNPJ da NF e motivo principal."""
import datetime

import analise_nf
import app_dados as dados
import correio
import hospedes
import prazos
from controle_nf import conferir_conteudo, documento_diferente, documento_tomador, documento_valido

AGORA = datetime.datetime(2026, 10, 9, 12, 0)


# ---------- prazo ----------
def test_prazo_por_tipo_em_dias_corridos():
    assert prazos.vencimento("2026-10-09T08:00:00", ["corrigir", "pedido_nf"])["vence"] == "2026-10-10T08:00:00"
    assert prazos.vencimento("2026-10-09T08:00:00", ["cobranca"])["horas"] == 24
    p = prazos.vencimento("2026-10-10T09:00:00", ["pedido_nf"])   # sábado conta
    assert p["vence"] == "2026-10-12T09:00:00" and p["tipo"] == "pedido"


def test_prazo_verde_ambar_vermelho():
    p = prazos.vencimento("2026-10-09T11:00:00", ["corrigir"])
    assert prazos.situacao(p, AGORA)[0] == "ok"
    assert prazos.situacao(prazos.vencimento("2026-10-08T22:00:00", ["corrigir"]), AGORA)[0] == "perto"
    assert prazos.situacao(prazos.vencimento("2026-10-08T08:00:00", ["corrigir"]), AGORA) == ("vencido", -4.0)


# ---------- pedidos ----------
def pedido(chave, email, cpf, checkin="10/10/2026", valor="300", carimbo="09/10/2026 08:00:00", aba="Hotel A",
           situacao="na_fila", data="2026-10-09"):
    return {"chave": chave, "aba": aba, "hotel": aba, "email": email, "emails": [], "carimbo": carimbo, "data": data,
            "nome": chave, "linha": chave, "situacao": situacao, "nfs": [], "envio_pendente": False,
            "campos": [("Documento Tomador", cpf), ("Check-in da Hospedagem", checkin), ("Valor da Nota Fiscal", valor)]}


def test_hospede_unico_por_email_ou_cpf():
    fila = [pedido("a", "ana@x.com", "123.456.789-09"), pedido("b", "financeiro@empresa.com", "123.456.789-09", checkin="20/09/2026"),
            pedido("c", "ana@x.com", "987.654.321-00", checkin="01/09/2026"), pedido("d", "outro@y.com", "111.444.777-35")]
    hospedes.marcar(fila, AGORA)
    assert len({s["hospede"] for s in fila[:3]}) == 1 and fila[3]["hospede"] != fila[0]["hospede"]
    assert {o["chave"] for o in fila[0]["outros_pedidos"]} == {"b", "c"}


def test_cnpj_de_empresa_com_muita_gente_nao_junta_funcionarios():
    fila = [pedido(f"p{i}", f"func{i}@empresa.com", "07.796.330/0001-84", checkin=f"0{i + 1}/09/2026") for i in range(4)]
    hospedes.marcar(fila, AGORA)
    assert len({s["hospede"] for s in fila}) == 4


def test_pedido_repetido_junta_e_conta_um():
    fila = [pedido("novo", "ana@x.com", "123.456.789-09", carimbo="09/10/2026 08:03:00"),
            pedido("velho", "ana@x.com", "123.456.789-09", carimbo="09/10/2026 08:00:00")]
    hospedes.marcar(fila, AGORA)
    assert fila[0]["repetido_de"] == "velho" and [r["chave"] for r in fila[1]["repetidos"]] == ["novo"]
    assert fila[1]["outros_pedidos"] == []   # o repetido não aparece de novo como "outro pedido"
    assert fila[1]["prazo"]["vence"] == "2026-10-11T08:00:00"


def test_principal_e_o_que_andou_mais():
    fila = [pedido("sem", "ana@x.com", "123.456.789-09", carimbo="09/10/2026 08:00:00"),
            pedido("comnf", "ana@x.com", "123.456.789-09", carimbo="09/10/2026 09:00:00", situacao="concluida")]
    hospedes.marcar(fila, AGORA)
    assert fila[0]["repetido_de"] == "comnf"


def test_nota_dividida_com_valores_diferentes_nao_e_repetido():
    fila = [pedido("parte1", "andiara@x.com", "123.456.789-09", valor="270"),
            pedido("parte2", "andiara@x.com", "123.456.789-09", valor="280", carimbo="09/10/2026 08:05:00")]
    hospedes.marcar(fila, AGORA)
    assert not fila[0]["repetido_de"] and not fila[1]["repetido_de"]


def test_sem_prazo_em_tratativa_e_resolvido():
    fila = [pedido("t", "a@x.com", "123.456.789-09", situacao="tratativa"),
            pedido("ok", "b@x.com", "111.444.777-35", situacao="concluida")]
    hospedes.marcar(fila, AGORA)
    assert fila[0]["prazo"] is None and fila[1]["prazo"] is None


# ---------- CPF/CNPJ da NF ----------
DANFSE = """CHAVE DE ACESSO DA NFS-E
23044001253440771000166000000000073626080528859692
CNPJ/CPF/NIF
53.440.771/0001-66
PRESTADOR/FORNECEDOR
Código IBGE/CEP
163.440.258-83
3550308/03295-000
TOMADOR/ADQUIRENTE
CNPJ/CPF/NIF
Nome/Nome Empresarial
Alexandre Galache
DATA DE CHECK-IN: 19/08/2026
DATA DE CHECK-OUT: 20/08/2026
VALOR DA DIÁRIA: R$ 237,40""" + "\n" * 5 + "x" * 200


def test_le_o_documento_do_tomador_e_nao_o_do_hotel():
    assert documento_tomador(DANFSE) == "16344025883"
    assert documento_tomador("sem rótulo 163.440.258-83") == ""


def test_digito_verificador():
    assert documento_valido("014.154.664-67") and not documento_valido("014.154.764-67")
    assert documento_valido("86.527.934/0001-00") and not documento_valido("86.527.935/0001-00")
    assert not documento_valido("111.111.111-11")


def test_nf_com_outro_cpf_valido_vira_alerta():
    sol = {"documentos": ["06315502598"]}
    assert documento_diferente(sol, DANFSE).startswith("⚠ CPF/CNPJ da NF (163.440.258-83) diferente do pedido")
    assert documento_diferente({"documentos": ["16344025883"]}, DANFSE) == ""


def test_formulario_digitado_errado_so_avisa():
    r = documento_diferente({"documentos": ["16344025884"]}, DANFSE)   # dígito errado no formulário
    assert r.startswith("CPF/CNPJ do formulário") and "⚠" not in r


def test_conferencia_continua_casando_e_leva_o_alerta():
    sol = {"documentos": ["06315502598"], "valores": ["237,40"], "datas": ["19/08/2026"], "nomes": ["Alexandre Galache"]}
    resultado, provas = conferir_conteudo(sol, DANFSE)
    assert resultado == "confere" and "⚠ CPF/CNPJ da NF" in provas


def test_painel_le_o_alerta_e_some_com_esta_certo():
    est = dados.estado_inicial()
    est["nfs"] = ["736"]
    est["obs"] = [{"quando": "", "agente": "robô", "texto": "NF 736 confirmada automaticamente: valor R$ 237,40 confere · "
                   "⚠ CPF/CNPJ da NF (163.440.258-83) diferente do pedido (063.155.025-98) · achada no Dropbox (João)"}]
    urgentes, avisos = dados.alertas_documento(est)
    assert urgentes == [{"nf": "736", "texto": "CPF/CNPJ da NF (163.440.258-83) diferente do pedido (063.155.025-98)"}]
    est["obs"].append({"quando": "", "agente": "Clara", "texto": "Conferido: CPF/CNPJ da NF 736 está certo"})
    assert dados.alertas_documento(est) == ([], [])


def test_alerta_poe_o_email_do_hospede_em_urgencia():
    e = {"id": "1", "pasta": "entrada", "caixa": "h@hotel", "de": "ana@x.com", "assunto": "NF", "quando": "2026-10-09T10:00:00",
         "classes": ["pedido_nf"], "nome": "Ana", "hotel": "A", "pc": "PC1"}
    entrada, _, _ = correio.juntar([e], {}, AGORA, {"ana@x.com": "NF 736: CPF/CNPJ da NF diferente"})
    assert entrada[0]["urgente"] and entrada[0]["motivo_urgencia"].startswith("NF 736")
    entrada, _, _ = correio.juntar([e], {}, AGORA)
    assert not entrada[0]["urgente"]
    c = correio.conversas(entrada)[0]
    assert c["prazo"]["vence"] == "2026-10-11T10:00:00"


# ---------- motivo principal ----------
def test_motivo_principal_e_o_primeiro_citado():
    p = analise_nf.pedido_do_cliente("Correção da nota", "Precisa constar na descrição a rubrica e o Pronac 123. "
                                                         "O valor também está errado: R$ 366,00.")
    motivo, detalhe, outros = analise_nf.motivo_principal(p)
    assert motivo == "descrição da nota" and "rubrica" in detalhe and "pronac" in detalhe
    assert outros == ["valor da nota"]


def test_motivo_sem_detalhe_e_comparacao_do_cpf():
    p = analise_nf.pedido_do_cliente("Cancelar NF", "Por favor cancelem a nota.")
    assert analise_nf.motivo_principal(p)[0] == "cancelar a nota"
    p = analise_nf.pedido_do_cliente("", "O CPF certo é 063.155.025-98")
    assert analise_nf.comparar(p, {"documento": "16344025883"})[0].startswith("⚠ cliente escreveu 063.155.025-98")


def test_analise_compacta_vai_e_volta_da_planilha():
    a = analise_nf.completo(analise_nf.pedido_do_cliente("", "valor errado"), {"valor": "190,00"}, "1221", "")
    resumo, d = analise_nf.ler_compacto(analise_nf.compacto(a))
    assert resumo == a["resumo"] and d["m"] == "valor da nota" and d["nf"].startswith("Na NF 1221: R$ 190,00")
    assert analise_nf.ler_compacto("frase antiga") == ("frase antiga", None)


def test_motivo_ignora_o_que_o_cliente_diz_que_esta_certo():
    texto = ("A primeira NF enviada, no valor de R$ 366,00, estava com o valor correto. No entanto, faltou incluir na nota "
             "a descrição, contendo a rubrica, o nome do projeto e o número do Pronac. Por esse motivo, solicitei apenas a "
             "correção da descrição. A outra nota ficou com o valor incorreto.\n-- \nNatália\nAviso de confidencialidade: "
             "documentos anexos")
    motivo, detalhe, outros = analise_nf.motivo_principal(analise_nf.pedido_do_cliente("Correção da NF – R$ 366,00", texto))
    assert motivo == "descrição da nota" and "pronac" in detalhe and outros == ["valor da nota"]
