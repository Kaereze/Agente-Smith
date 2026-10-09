import analise_nf as a

DANFSE = """DANFSe v2.0
1221
Número da NFS-e
COMPETÊNCIA DA NFS-E
29/09/2026
DATA E HORA DA EMISSÃO DA NFS-E
29/09/2026
TOMADOR / ADQUIRENTE CNPJ / CPF / NIF
08.183.347/0001-29
DATA DE CHECK-IN: 29/09/2026
DATA DE CHECK-OUT: 30/09/2026
QUANTIDADE DE DIÁRIAS: 1
VALOR LÍQUIDO DA NFS-e
R$ 190,00"""


def test_le_o_danfse():
    d = a.dados_do_pdf(DANFSE)
    assert (d["valor"], d["competencia"], d["checkin"], d["checkout"], d["documento"]) == \
        ("190,00", "29/09/2026", "29/09/2026", "30/09/2026", "08.183.347/0001-29")


def test_pedido_do_cliente():
    p = a.pedido_do_cliente("Correção da NF 1221", "A nota saiu com R$ 190,00 mas o certo é R$ 380,00, foram 2 diárias.")
    assert "valor" in p["motivos"] and p["valores"] == ["190,00", "380,00"] and p["nfs"] == ["1221"]


def test_resumo_cruza_o_que_o_cliente_diz_com_a_nota():
    p = a.pedido_do_cliente("NF errada", "O valor está errado: veio R$ 190,00 e deveria ser R$ 380,00.")
    r = a.resumo(p, a.dados_do_pdf(DANFSE), "1221")
    assert "R$ 190,00" in r and "pede R$ 380,00" in r and "NF 1221" in r
    p = a.pedido_do_cliente("NF", "A data está errada, fiquei de 02/10/2026 a 04/10/2026")
    assert "não está na nota" in a.resumo(p, a.dados_do_pdf(DANFSE), "1221")
    assert "conferir à mão" in a.resumo(p, None, "")


def test_nf_anexada_ao_email_vale_primeiro_e_o_nome_do_arquivo_da_o_numero():
    texto_ocr = "DADOS DA NFSe\nNúmero I Série\nValor Total\nR$ 366,00"
    r = a.analisar({"assunto": "Correção da NF", "nome": "Ana"}, "o valor de R$ 366,00 está certo, falta a descrição",
                   [], (), [("NF 6524 - CARLA LUIZA - 96816.pdf", texto_ocr)])
    assert "NF 6524" in r["resumo"] and "R$ 366,00" in r["resumo"] and "anexada" in r["resumo"]


def test_mesmo_numero_em_dois_hoteis_vale_o_do_nome():
    itens = [("NF 100 - JOSE SILVA - 1.pdf", r"C:\D\LUXOR\x.pdf", 1, ("100", "JOSE SILVA")),
             ("NF 100 - MARIA SOUZA - 2.pdf", r"C:\D\BAHIA\y.pdf", 2, ("100", "MARIA SOUZA"))]
    assert a.achar_nf(["100"], "Maria Souza", "", itens)[0].startswith("NF 100 - MARIA")
    assert a.achar_nf(["100"], "", "LUXOR", itens)[0].startswith("NF 100 - JOSE")
