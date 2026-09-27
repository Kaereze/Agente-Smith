"""Casos tirados da Planilha Central de verdade (formulário novo, carimbo só com data)."""
from conftest import CENTRAL
from main import executar
from modelos import Hotel
from montar_email import montar_emails
from sheets import interpretar_aba, ler_hoteis, marcar_enviados, nome_do_hotel_pela_aba

CAB_NOVO = ['Carimbo de data/hora', 'Termos de aceite', 'Documento Tomador', 'Nome Tomador', 'CEP', 'E-mail',
            'Telefone para contato', 'CPF do Titular da Reserva', 'Nome do Titular da Reserva',
            'Check-in da Hospedagem', 'Check-out da Hospedagem', 'Informações necessárias na Nota Fiscal',
            'Descrição específica', 'Nota Dividida', 'Dividida em quantas vezes', 'Hóspedes Acompanhantes',
            'Valor da Nota Fiscal', 'Enviado']
ABA_MERCADO = "Solicitação Nota Fiscal (MERCADO) (respostas)"


def linha_nova(email="ana@x.com", doc="1234567000199", valor="R$ 500,00", enviado="FALSE"):
    return ["5/28/2026", "Aceito", doc, "Ana Souza Lima", "1310000", email, "11999999999", "1234567890",
            "Ana Souza", "5/20/2026", "5/22/2026", "", "", "Sim", "2", "", valor, enviado]


def test_formulario_novo(cfg):
    hotel = Hotel(ABA_MERCADO, "MERCADO", "op@x", "P")
    [s], erro = interpretar_aba(hotel, [CAB_NOVO, linha_nova()], cfg)
    campos = dict(s.campos)
    assert erro is None
    assert s.email_hospede == "ana@x.com"
    assert s.nome_titulo == "Ana Souza Lima"
    assert campos["Documento Tomador"] == "01234567000199"       # CNPJ com zero
    assert campos["CPF do Titular da Reserva"] == "01234567890"
    assert campos["CEP"] == "01310000"
    assert campos["Check-in da Hospedagem"] == "20/05/2026"
    assert campos["Dividida em quantas vezes"] == "2"
    assert "E-mail" not in campos and "Termos de aceite" not in campos and "Enviado" not in campos
    assert "Informações necessárias na Nota Fiscal" not in campos  # vazio


def test_documento_tomador_com_cpf(cfg):
    hotel = Hotel(ABA_MERCADO, "MERCADO", "op@x", "P")
    [s], _ = interpretar_aba(hotel, [CAB_NOVO, linha_nova(doc="987654321")], cfg)
    assert dict(s.campos)["Documento Tomador"] == "00987654321"


def test_nome_do_hotel_sai_do_nome_da_aba():
    assert nome_do_hotel_pela_aba(ABA_MERCADO) == "MERCADO"
    assert nome_do_hotel_pela_aba("Nota Fiscal (São Francisco) (respostas)") == "São Francisco"
    assert nome_do_hotel_pela_aba("Status") == "Status"


def _nomes_e_agentes(hoteis):
    return {(h.nome, h.operador) for h in hoteis}


def test_cadastro_liga_aba_ao_agente(cfg, planilha):
    planilha.planilhas[CENTRAL]["Cadastro_Hoteis"] += [["MERCADO", "notafiscal@mercado", "Cristian"],
                                                       ["GV", "notafiscal@gv", "Bernardo"]]
    planilha.planilhas[CENTRAL][ABA_MERCADO] = [CAB_NOVO]
    planilha.planilhas[CENTRAL]["Solicitação Nota Fiscal (Governador Valadares) (respostas)"] = [CAB_NOVO]
    planilha.planilhas[CENTRAL]["Solicitação Nota Fiscal (TesteEdu) (respostas)"] = [CAB_NOVO]
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert ("MERCADO", "notafiscal3@andradehoteis.com.br") in _nomes_e_agentes(hoteis)
    assert ("GV", "notafiscal4@andradehoteis.com.br") in _nomes_e_agentes(hoteis)   # pelo apelido
    assert not any("TesteEdu" in h.aba for h in hoteis) and erros == []            # ignorada, sem erro
    assert all("(respostas)" in h.aba for h in hoteis)                             # Cadastro/Status não são hotel


def test_aba_de_hotel_fora_do_cadastro_vira_erro(cfg, planilha):
    planilha.planilhas[CENTRAL]["Solicitação Nota Fiscal (Hotel Novo) (respostas)"] = [CAB_NOVO]
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert len(erros) == 1 and "Hotel Novo" in erros[0]


def test_agente_sem_email(cfg, planilha):
    cfg["agentes"]["Clara"] = ""
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert not any(h.nome == "ARACAJU" for h in hoteis)
    assert len(erros) == 1 and "Clara" in erros[0]

    cfg["modo"] = "SIMULACAO"  # na simulação, aparece com aviso em vez de sumir
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert any(h.nome == "ARACAJU" and "não configurado" in h.operador for h in hoteis) and erros == []


def test_cadastro_com_linha_de_cabecalho(cfg, planilha):
    planilha.planilhas[CENTRAL]["Cadastro_Hoteis"].insert(0, ["Hotel", "E-mail", "Agente"])
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert len(hoteis) == 3 and erros == []


def test_mesmo_hospede_dois_pedidos_no_mesmo_dia_nao_marca_o_que_nao_foi(cfg, planilha, outlook):
    """
    O carimbo vem só com a data. Um 2º pedido do mesmo hóspede chega DEPOIS
    da leitura e ANTES da marcação: ele não pode ser marcado TRUE sem ir.
    """
    hotel = Hotel(ABA_MERCADO, "MERCADO", "op@x", CENTRAL)
    planilha.planilhas[CENTRAL][ABA_MERCADO] = [CAB_NOVO, linha_nova(valor="R$ 500,00")]
    enviados, _ = interpretar_aba(hotel, planilha.aba(ABA_MERCADO), cfg)

    planilha.aba(ABA_MERCADO).append(linha_nova(valor="R$ 900,00"))  # chegou no meio
    marcar_enviados(planilha, cfg, enviados)

    enviado = CAB_NOVO.index("Enviado")
    assert [l[enviado] for l in planilha.aba(ABA_MERCADO)[1:]] == ["TRUE", "FALSE"]


def test_fluxo_completo_com_formulario_novo(cfg, planilha, outlook):
    planilha.aba("Cadastro_Hoteis").append(["MERCADO", "notafiscal@mercado", "Cristian"])
    planilha.planilhas[CENTRAL][ABA_MERCADO] = [CAB_NOVO, linha_nova(), linha_nova(valor="R$ 900,00"),
                                                linha_nova(email="bia@x.com", enviado="TRUE")]
    assert executar(cfg, planilha, outlook, esperar=lambda s: None) == 0
    [email] = [e for e in outlook.enviados if e.operador == "notafiscal3@andradehoteis.com.br"]
    assert len(email.solicitacoes) == 2 and email.assunto == "Solicitações NF (2) - MERCADO"
    enviado = CAB_NOVO.index("Enviado")
    assert [l[enviado] for l in planilha.aba(ABA_MERCADO)[1:]] == ["TRUE", "TRUE", "TRUE"]


def test_aba_colada_com_data_brasileira(cfg):
    """Dados colados à mão (aba do Ondina) vêm dd/mm; os do Forms vêm mm/dd."""
    hotel = Hotel(ABA_MERCADO, "MERCADO", "op@x", "P")
    linhas = [CAB_NOVO, ["26/10/2025 12:36:33"] + linha_nova()[1:], ["05/10/2025"] + linha_nova(email="b@x")[1:]]
    pend, _ = interpretar_aba(hotel, linhas, cfg)
    assert {s.formato_data for s in pend} == {"brasileiro"}
    html = montar_emails(pend, cfg)[0].html
    assert "05/10/2025" in html and "10/05/2025" not in html


def test_modo_teste_nao_exige_email_do_agente(cfg, planilha):
    cfg["modo"], cfg["agentes"]["Clara"] = "TESTE", ""
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert any(h.nome == "ARACAJU" for h in hoteis) and erros == []


def test_somente_hoteis(cfg, planilha, outlook):
    cfg["somente_hoteis"] = ["aracaju"]
    assert executar(cfg, planilha, outlook, esperar=lambda s: None) == 0
    assert {s.hotel.nome for e in outlook.enviados for s in e.solicitacoes} == {"ARACAJU"}


def test_somente_hoteis_nao_gera_erro_dos_outros(cfg, planilha):
    cfg["somente_hoteis"], cfg["agentes"]["João"] = ["ARACAJU"], ""   # João (Estrela, Barra) sem e-mail
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert [h.nome for h in hoteis] == ["ARACAJU"] and erros == []
