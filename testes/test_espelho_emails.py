import datetime

import espelho_emails as ee

D = datetime.datetime


def test_corta_o_historico_colado_embaixo():
    texto = "Boa tarde,\nPreciso da nota no CNPJ 12.345.678/0001-90.\nObrigada\n\nDe: notafiscal@hotel.com\nEnviada em: ..."
    assert ee.sem_historico(texto) == "Boa tarde,\nPreciso da nota no CNPJ 12.345.678/0001-90.\nObrigada"
    assert ee.sem_historico("Oi\n\nEm seg., 5 de out. de 2026 às 10:00, Hotel <a@b> escreveu:\n> antigo") == "Oi"
    assert ee.sem_historico("só o texto") == "só o texto"


def test_automaticos_e_listas_ficam_de_fora():
    assert ee.e_automatico("no-reply@booking.com") and ee.e_automatico("naoresponda@banco.com.br")
    assert ee.e_automatico("reservas@decolar.com") and ee.e_automatico("x@empresa.com", "List-Unsubscribe: <mailto:..>")
    assert ee.e_automatico("sem-arroba")
    assert not ee.e_automatico("maria.souza@gmail.com") and not ee.e_automatico("financeiro@empresa.com.br")


def test_respondido_sai_da_lista_so_se_a_resposta_for_depois():
    pend = {"a": {"de": "ana@x.com", "recebido": "2026-10-06T10:00:00"},
            "b": {"de": "bia@x.com", "recebido": "2026-10-06T10:00:00"},
            "c": {"de": "caio@x.com", "recebido": ""}}
    enviados = {"ana@x.com": D(2026, 10, 6, 11, 0), "bia@x.com": D(2026, 10, 6, 9, 0)}
    assert sorted(ee.resolver_pendentes(pend, enviados)) == ["b", "c"]


def test_aba_ida_e_volta():
    pend = {"x1": {"id": "x1", "caixa": "nf@hotel.com", "hotel": "LUXOR", "de": "ana@x.com", "nome": "Ana",
                   "assunto": "Nota", "recebido": "2026-10-06T10:00:00", "anexos": ["a.pdf", "b.pdf"], "texto": "Oi"}}
    linhas = ee.linhas_da_aba(pend, "PC-A", D(2026, 10, 6, 12, 0))
    assert linhas[0] == ee.CABECALHO
    e = ee.ler_aba(linhas)[0]
    assert (e["id"], e["hotel"], e["anexos"], e["pc"]) == ("x1", "LUXOR", ["a.pdf", "b.pdf"], "PC-A")


def test_voucher_com_dois_quartos_e_nota_dividida():
    from controle_nf import quartos_da_reserva
    recibo = ("Recibo\nN° do itinerário da Hoteis.com: 72077571275512\n2 quartos para 3 diárias\nQuarto duplo econômico\n"
              "Reserva feita para: Lorena Perego Mendonça\nQuarto duplo econômico\nReserva feita para: José Eduardo Canteli\n"
              "Preço do quarto 1\nPreço do quarto 2\nTotal R$ 1.218,75")
    assert quartos_da_reserva(recibo) == (2, ["Lorena Perego Mendonça", "José Eduardo Canteli"])
    voucher = "Detalhes do quarto\nQuarto duplo\nReservado para\nMaria Silva, 2 adultos\nPreço do quarto 1\nTotal"
    assert quartos_da_reserva(voucher) == (1, ["Maria Silva"])
    assert quartos_da_reserva("Boa tarde, segue o comprovante de pagamento.") == (0, [])


def test_quartos_vao_e_voltam_pela_aba():
    import datetime
    import espelho_emails as esp
    p = {"x": {"id": "x", "caixa": "nf@h.com", "hotel": "BOA VIAGEM", "de": "a@b.com", "nome": "A", "assunto": "NF",
               "recebido": "2026-10-06T18:14:32", "anexos": ["voucher.pdf"], "texto": "oi",
               "quartos": [2, ["Lorena Perego Mendonça", "José Eduardo Canteli"]]},
         "y": {"id": "y", "caixa": "nf@h.com", "hotel": "BOA VIAGEM", "de": "c@d.com", "nome": "C", "assunto": "Oi",
               "recebido": "2026-10-06T10:00:00", "anexos": [], "texto": "oi"}}
    lidos = {e["id"]: e for e in esp.ler_aba(esp.linhas_da_aba(p, "PC-A", datetime.datetime(2026, 10, 7)))}
    assert lidos["x"]["quartos"] == 2 and lidos["x"]["hospedes_quartos"] == ["Lorena Perego Mendonça", "José Eduardo Canteli"]
    assert lidos["y"]["quartos"] == 0 and lidos["y"]["hospedes_quartos"] == []
    antiga = [esp.CABECALHO[:11], ["z", "c", "h", "d", "n", "s", "2026-10-06T10:00:00", "", "t", "PC", "agora"]]
    assert esp.ler_aba(antiga)[0]["quartos"] == 0   # aba de PC ainda sem a coluna nova
