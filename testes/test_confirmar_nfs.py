import datetime

import app_dados as d
import confirmar_nfs as c

NOTA = ("NOTA FISCAL DE SERVIÇO " * 12 +
        " TOMADOR Maria Souza Lima CPF 012.345.678-90 Descrição do Serviço "
        "DATA DE CHECK-IN: 20/09/2026 DATA DE CHECK-OUT: 22/09/2026 VALOR DA DIÁRIA: R$ 300,00")


def sol(nome="Maria Souza Lima", data="2026-09-21", partes=1, cpf="01234567890", email="maria@x.com", aba="A"):
    return {"chave": d.chave(aba, "9/21/2026 10:00:00", email), "aba": aba, "hotel": "BARRA", "linha": 2,
            "carimbo": "9/21/2026 10:00:00", "email": email, "nome": nome, "data": data, "enviado": True,
            "partes": partes, "emails": [email], "nomes": [nome], "email_hotel": "nf@barra.com",
            "campos": [("CPF Tomador", cpf), ("Check-in da Hospedagem", "20/09/2026"),
                       ("Check-out da Hospedagem", "22/09/2026"), ("Informações necessárias na Nota Fiscal", "Valor Diárias")]}


def test_registro_pula_concluidas_e_antigas():
    s1, s2, s3 = sol(), sol(nome="Outra Pessoa", email="o@x.com"), sol(data="2026-01-01", email="v@x.com")
    estados = d.dobrar_eventos([d.CABECALHO_TRATAMENTO,
                                d.evento(datetime.datetime(2026, 9, 25), "Clara", "PC", "A", s2["carimbo"], "o@x.com", d.NF, "9")])
    reg = c.registro_da_central([s1, s2, s3], estados, "2026-08-01")
    assert list(reg.solicitacoes) == [s1["chave"]]
    assert reg.solicitacoes[s1["chave"]]["documentos"] == ["01234567890"]


def test_nf_parcial_entra_com_a_nf_que_ja_tem():
    s = sol(partes=2)
    estados = d.dobrar_eventos([d.CABECALHO_TRATAMENTO,
                                d.evento(datetime.datetime(2026, 9, 25), "Clara", "PC", "A", s["carimbo"], s["email"], d.NF, "9")])
    reg = c.registro_da_central([s], estados, "2026-08-01")
    assert list(reg.solicitacoes[s["chave"]]["nfs"]) == ["9"]
    assert c._novas_nfs(reg, {(s["chave"], "9")}) == []


def test_nota_do_dropbox_confirma_pelo_conteudo():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    antes = set()
    reg.aplicar_nota_dropbox(r"X:\NF 643 - MARIA SOUZA LIMA - 70001.pdf", ("643", "MARIA SOUZA LIMA"),
                             datetime.datetime(2026, 9, 26, 9), lambda: NOTA, "PC 1 - JOÃO")
    achadas = c._novas_nfs(reg, antes)
    assert [(k, n) for k, n, _ in achadas] == [(s["chave"], "643")]
    assert "CPF do tomador confere" in achadas[0][2]


def test_nota_de_outra_estadia_nao_confirma():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    outra = NOTA.replace("20/09/2026", "10/05/2026").replace("22/09/2026", "12/05/2026")
    reg.aplicar_nota_dropbox("X:\\NF 1 - MARIA.pdf", ("1", "MARIA SOUZA LIMA"),
                             datetime.datetime(2026, 9, 26), lambda: outra, "PC 1")
    assert c._novas_nfs(reg, set()) == []


def test_email_de_nf_para_o_hospede_confirma():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    reg.aplicar_envio({"entry_id": "E1", "conta": "nf@barra.com", "destinatarios": {"maria@x.com"},
                       "assunto": "NF 700 - MARIA SOUZA LIMA", "data": datetime.datetime(2026, 9, 26),
                       "anexos": ["NF 700.pdf"]}, ["pdf"], ler_texto=lambda: NOTA)
    assert [(n) for _, n, _ in c._novas_nfs(reg, set())] == ["700"]


def test_nf_ilegivel_nao_e_publicada():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    reg.aplicar_envio({"entry_id": "E1", "conta": "nf@barra.com", "destinatarios": {"maria@x.com"},
                       "assunto": "NF 700 - MARIA SOUZA LIMA", "data": datetime.datetime(2026, 9, 26),
                       "anexos": ["NF 700.pdf"]}, ["pdf"], ler_texto=lambda: "")
    assert c._novas_nfs(reg, set()) == []


def test_indice_por_nome_email_e_conta():
    s1, s2 = sol(), sol(nome="Jose Pereira", email="jose@x.com", aba="B")
    idx = c.Indice(c.registro_da_central([s1, s2], {}, "2026-08-01"))
    assert idx.por_nome("MARIA SOUZA LIMA") == {s1["chave"]}
    assert idx.por_nome("MARIA SOUZA") == {s1["chave"]}
    assert idx.por_nome("ANA COSTA") == set()
    assert idx.para_email({"jose@x.com"}, "outra@conta", "QUALQUER") == {s2["chave"]}
    assert idx.para_email({"x@y.com"}, "nf@barra.com", "MARIA SOUZA") == {s1["chave"]}
    assert idx.para_email({"x@y.com"}, "outra@conta", "MARIA SOUZA") == set()


def test_nf_achada_no_sub_registro_aparece_no_registro_completo():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    idx = c.Indice(reg)
    idx.sub(idx.por_nome("MARIA SOUZA LIMA")).aplicar_nota_dropbox(
        "X:\\NF 643 - MARIA SOUZA LIMA.pdf", ("643", "MARIA SOUZA LIMA"), datetime.datetime(2026, 9, 26), lambda: NOTA, "PC 1")
    assert [n for _, n, _ in c._novas_nfs(reg, set())] == ["643"]
