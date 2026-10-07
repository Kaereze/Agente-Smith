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
