"""✅ só com prova de dentro da nota (PDF/OCR/XML) — caso real da NF 801 (Ondina, 24/09/2026)."""
import datetime

from controle_nf import Registro, conferir_conteudo, nfs_sem_prova, provas_da_solicitacao, reconferir, situacao
from modelos import Hotel, Solicitacao

# Imita o texto que o OCR do Windows devolveu (com os erros dele: "f" no lugar de "/", "OO" no lugar de "00")
NOTA_OCR = """PREFEITURA MUNICIPAL DO SALVADOR NOTA FISCAL DE SERVIÇOS ELETRÔNICA
Número da Nota: 00000801  Data e Hora de Emissão: 18f09f2026
PRESTADOR DE SERVIÇOS CPF/CNPJ 47.391.837f0001-72 REDE ANDRADE ONDINA HOTEL LTDA
TOMADOR DE SERVIÇOS / ADQUIRENTE Nome/Razão Social: EMPRESA TESTE MATERIAL PLASTICO LTDA
CPF/CNPJ 26.295.687f0001-23 Endereço: Salvador - CEP: 40140-130 - BA
DISCRIMINAÇÃO DOS SERVIÇOS DATA DE CHECK-OUT: 15/09/2026 QUANTIDADE DE DIÁRIAS: 1
VALOR DA DIÁRIA: R$ 153,00 (APTO 202 + APTO 307) VALOR TOTAL DA NOTA = R$306,OO
CNAE 5510801 - Hotéis Item da Lista de Serviços: 00901 - Hospedagem de qualquer natureza em hotéis"""

HOTEL = Hotel("aba", "ONDINA", "op@x", "P", "notafiscal@ondina.com.br", "João")


def _sol(campos, nomes=("Léa Montes Ferreira",)):
    s = Solicitacao(hotel=HOTEL, linha=133, carimbo="18/09/2026", email_hospede="lea@x.com", nome_titulo=nomes[0],
                    campos=campos)
    s.nomes = list(nomes)
    return {**provas_da_solicitacao(s), "nomes": list(nomes), "partes": 1, "nfs": {}, "tratativas": {}}


def test_provas_tiradas_da_solicitacao():
    sol = _sol([("CNPJ Tomador", "26295687000123"), ("Descrição específica", "diária no valor de R$ 306,00"),
                ("Check-in da Hospedagem", "14/09/2026"), ("Documento do Hóspede", "86224506")])
    assert sol["documentos"] == ["26295687000123"]      # RG de 8 dígitos não entra
    assert sol["valores"] == ["306,00"] and sol["datas"] == ["14/09/2026"]


def test_cnpj_do_tomador_na_nota_confere_mesmo_com_ocr_torto():
    sol = _sol([("CNPJ Tomador", "26295687000123")])
    resultado, prova = conferir_conteudo(sol, NOTA_OCR)
    assert resultado == "confere" and "CNPJ do tomador confere" in prova


def test_valor_mais_data_confere_sem_documento():
    sol = _sol([("Descrição específica", "diária de R$ 306,00"), ("Check-out da Hospedagem", "15/09/2026")])
    assert conferir_conteudo(sol, NOTA_OCR)[0] == "confere"


def test_nota_de_outro_tomador_nao_confere():
    sol = _sol([("CNPJ Tomador", "11111111000191"), ("Descrição específica", "R$ 999,00")], nomes=("Fulano Beltrano",))
    assert conferir_conteudo(sol, NOTA_OCR)[0] == "nao_confere"


def test_nota_ilegivel_fica_pra_conferir():
    assert conferir_conteudo(_sol([]), "   ")[0] == "sem_texto"


def _registro(sol):
    r = Registro()
    r.solicitacoes["NF-A-01"] = {**sol, "codigo": "NF-A", "hotel": "ONDINA", "email_hotel": "notafiscal@ondina.com.br",
                                 "data_pedido": "2026-09-18", "emails": ["lea@x.com"], "nome": "Léa"}
    r.emails["NF-A"] = {"destinatario": "op@x", "assunto": "", "refs": ["NF-A-01"], "precisa_atualizar": False}
    return r


def _envio(entry="E1"):
    return {"entry_id": entry, "conta": "notafiscal@ondina.com.br", "destinatarios": {"lea@x.com"},
            "assunto": "NF 801 - KESYA NUNES SANTOS - 66887", "data": datetime.datetime(2026, 9, 18, 15, 40),
            "anexos": ["NF 801.pdf", "image001.png"]}


def test_nome_diferente_no_assunto_mas_nota_do_mesmo_tomador_da_check():
    """O caso real: assunto com o nome da reserva (Kesya), nota do tomador da Léa -> é dela."""
    r = _registro(_sol([("CNPJ Tomador", "26295687000123")]))
    assert r.aplicar_envio(_envio(), ["pdf"], ler_texto=lambda: NOTA_OCR) == ("NF-A-01", "nf")
    tipo, texto = situacao(r.solicitacoes["NF-A-01"])
    assert tipo == "ok" and "CNPJ do tomador confere" in texto


def test_nota_de_outra_pessoa_pro_mesmo_email_nao_da_check():
    r = _registro(_sol([("CNPJ Tomador", "11111111000191")], nomes=("Fulano Beltrano",)))
    assert r.aplicar_envio(_envio(), ["pdf"], ler_texto=lambda: NOTA_OCR) is None
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "aguardando"


def test_nota_ilegivel_enviada_ao_email_do_pedido_conclui():
    """[05/10/2026] "se o email estiver com o anexo da nota pode concluir" — mesmo sem ler o PDF."""
    r = _registro(_sol([("CNPJ Tomador", "26295687000123")]))
    r.aplicar_envio(_envio(), ["pdf"], ler_texto=lambda: "")
    tipo, texto = situacao(r.solicitacoes["NF-A-01"])
    assert tipo == "ok" and "enviada ao e-mail do pedido" in texto


def test_nome_do_assunto_batendo_conclui_sem_abrir_o_pdf():
    """Caso real Maria Cleuza (NF 973, Ondina, 03/09/2026): PDF escaneado, OCR leu o CPF torto."""
    r = _registro(_sol([("CPF Tomador", "17556066568")], nomes=("Maria Cleuza Carvalho da Cruz",)))
    envio = {**_envio(), "assunto": "NF 973 - MARIA CLEUZA CARVALHO - 66479",
             "anexos": ["NF 973 - MARIA CLEUZA CARVALHO - 66479.pdf"]}
    abriu = []
    assert r.aplicar_envio(envio, ["pdf"], ler_texto=lambda: abriu.append(1) or "lixo") == ("NF-A-01", "nf")
    assert abriu == [] and list(r.solicitacoes["NF-A-01"]["nfs"]) == ["973"]


def test_dividida_com_dois_anexos_registra_as_duas_notas():
    r = _registro(_sol([], nomes=("Maria Cleuza Carvalho da Cruz",)))
    r.solicitacoes["NF-A-01"]["partes"] = 2
    envio = {**_envio(), "assunto": "NF 973 - MARIA CLEUZA",
             "anexos": ["NF 973 - MARIA CLEUZA.pdf", "NF 973 - MARIA CLEUZA.xml", "NF 974 - MARIA CLEUZA.pdf"]}
    r.aplicar_envio(envio, ["pdf", "xml"])
    assert sorted(r.solicitacoes["NF-A-01"]["nfs"]) == ["973", "974"]
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "ok"
    r2 = _registro(_sol([], nomes=("Maria Cleuza Carvalho da Cruz",)))
    r2.aplicar_envio({**envio, "anexos": ["nota1.pdf", "nota2.pdf"]}, ["pdf"])
    assert sorted(r2.solicitacoes["NF-A-01"]["nfs"]) == ["973", "973 (2º anexo)"]


def test_check_antigo_e_reconferido():
    r = _registro(_sol([("CNPJ Tomador", "11111111000191")], nomes=("Fulano Beltrano",)))
    r.solicitacoes["NF-A-01"]["nfs"]["801"] = {"data": "2026-09-18T15:40:00", "assunto": "NF 801", "entry_id": "E1"}
    assert nfs_sem_prova(r) == [("NF-A-01", "801", "E1")]
    assert reconferir(r, "NF-A-01", "801", NOTA_OCR)[0] == "nao_confere"
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "aguardando"        # ✅ desfeito
    assert r.emails["NF-A"]["precisa_atualizar"] is True                  # e-mail volta pro ⏳
    assert nfs_sem_prova(r) == []


def test_nota_do_dropbox_confere_pelo_conteudo():
    r = _registro(_sol([("CNPJ Tomador", "26295687000123")]))
    ref = r.aplicar_nota_dropbox("X:/PC 2 - CLARA/NF 801 - KESYA.pdf", ("801", "KESYA"),
                                 datetime.datetime(2026, 9, 18, 16, 0), lambda: NOTA_OCR, "PC 2 - CLARA")
    assert ref == "NF-A-01"
    tipo, texto = situacao(r.solicitacoes["NF-A-01"])
    assert tipo == "ok" and "Dropbox (PC 2 - CLARA)" in texto
    # a mesma nota não é aplicada duas vezes
    assert r.aplicar_nota_dropbox("X:/PC 2 - CLARA/NF 801 - KESYA.pdf", ("801", "KESYA"),
                                  datetime.datetime(2026, 9, 18, 16, 0), lambda: NOTA_OCR, "PC 2 - CLARA") is None


def test_nota_do_dropbox_de_outra_pessoa_nao_marca():
    r = _registro(_sol([("CNPJ Tomador", "11111111000191")], nomes=("Fulano Beltrano",)))
    assert r.aplicar_nota_dropbox("X:/NF 801.pdf", ("801", "KESYA"), datetime.datetime(2026, 9, 18, 16, 0),
                                  lambda: NOTA_OCR, "PC 1 - JOÃO") is None


def test_nota_do_dropbox_antes_do_pedido_nao_conta():
    r = _registro(_sol([("CNPJ Tomador", "26295687000123")]))
    assert r.aplicar_nota_dropbox("X:/NF 801.pdf", ("801", "K"), datetime.datetime(2026, 9, 10), lambda: NOTA_OCR,
                                  "PC 1 - JOÃO") is None


def test_mesmo_cnpj_outra_estadia_nao_e_a_nota():
    """Caso real 27/09: Consórcio Planex, pedido de 23/09 a 28/09, NF 1369 era da estadia de 18 a 19/09."""
    from controle_nf import conferir_conteudo
    sol = {"documentos": ["12345678000190"], "datas": ["23/09/2026", "28/09/2026"], "nomes": ["Consorcio Planex"],
           "valores": [], "servicos": ["diaria"]}
    nota = ("NOTA FISCAL DE SERVIÇO " * 10) + " Tomador CNPJ 12.345.678/0001-90 Consorcio Planex "
    nota += "Hospedagem diária período 18/09/2026 a 19/09/2026 emitida em 24/09/2026"
    res, prova = conferir_conteudo(sol, nota)
    assert res == "nao_confere" and "datas" in prova


def test_pediu_consumo_nota_de_diaria_nao_e_a_nota():
    """Hóspede pede diária ontem e consumo hoje com os mesmos dados: a NF da diária não fecha o pedido do consumo."""
    from controle_nf import conferir_conteudo
    sol = {"documentos": ["12345678901"], "datas": ["20/09/2026", "22/09/2026"], "nomes": ["Ze Silva"],
           "valores": [], "servicos": ["consumo"]}
    nota = ("NOTA FISCAL DE SERVIÇO " * 10) + " CPF 123.456.789-01 Ze Silva Hospedagem diária 20/09/2026 a 22/09/2026"
    res, prova = conferir_conteudo(sol, nota)
    assert res == "nao_confere" and "serviço diferente" in prova
    sol["servicos"] = ["diaria"]
    assert conferir_conteudo(sol, nota)[0] == "confere"


def test_hospede_errou_o_ano_da_estadia():
    """Caso real 27/09: 'Incomum viagens' digitou 25/09/0026; a NF 1201 (25/09/2026) é a certa."""
    from controle_nf import conferir_conteudo
    sol = {"documentos": ["12345678000190"], "datas": ["25/09/0026", "26/09/0026"], "nomes": ["Incomum viagens"],
           "valores": [], "servicos": ["diaria"]}
    nota = ("NOTA FISCAL DE SERVIÇO " * 10) + " CNPJ 12.345.678/0001-90 hospedagem diária 25/09/2026 27/09/2026"
    assert conferir_conteudo(sol, nota)[0] == "confere"


BLOCO_1202 = """Descrição do Serviço
DATA DE CHECK-IN: 24/09/2026
DATA DE CHECK-OUT: 25/10/2026
QUANTIDADE DE DIÁRIAS: 1
VALOR DA DIÁRIA: R$ 140,00
VALOR DO ESTACIONAMENTO: R$ 20,00
TRIBUTAÇÃO MUNICIPAL (ISSQN)"""


def test_le_a_descricao_do_servico_da_nota():
    from controle_nf import ler_descricao_nota
    d = ler_descricao_nota(BLOCO_1202)
    assert d == {"checkin": "24/09", "checkout": "25/10", "servicos": {"diaria", "estacionamento"}}
    d = ler_descricao_nota("DATA DE CHECK-IN: 18/09/2026\nVALOR DE DIARIA: R$148,77\nVALOR DO CONSUMO: R$ 0,00")
    assert d["servicos"] == {"diaria"}                 # consumo zerado não conta


def test_checkout_com_mes_errado_na_nota_ainda_confere():
    """NF 1202 real: check-out 25/10 (era 25/09) — o check-in 24/09 basta."""
    from controle_nf import conferir_conteudo
    sol = {"documentos": ["12345678000190"], "datas": ["24/09/2026", "25/09/2026"], "nomes": ["Crop"], "valores": [],
           "servicos": ["diaria", "estacionamento"]}
    texto = ("NOTA FISCAL " * 20) + " CNPJ 12.345.678/0001-90 " + BLOCO_1202
    res, prova = conferir_conteudo(sol, texto)
    assert res == "confere", prova


def test_pediu_so_consumo_e_a_nota_e_de_diaria_e_estacionamento():
    from controle_nf import conferir_conteudo
    sol = {"documentos": ["12345678000190"], "datas": ["24/09/2026", "25/09/2026"], "nomes": ["Crop"], "valores": [],
           "servicos": ["consumo"]}
    texto = ("NOTA FISCAL " * 20) + " CNPJ 12.345.678/0001-90 " + BLOCO_1202
    assert conferir_conteudo(sol, texto)[0] == "nao_confere"
