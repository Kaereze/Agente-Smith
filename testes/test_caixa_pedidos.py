"""Notas fiscais = espelho da Caixa de Entrada (usuário, 11/10/2026): só as solicitações do robô que estão no Outlook."""
import datetime

import app_dados as dados
import espelho_emails as ee

CORPO = """Solicitações de Nota Fiscal
Operador: notafiscal@redeandradelagoa.com.br · Gerado em 08/10/2026 19:24 · 2 solicitação(ões)
LAGOA (2 solicitações)
Solicitação 1 de 2 — Nivaldo Anderson Chaves da Silva
⏳ Aguardando NF [ref NF-0190947310-01]
Enviado por: anderson.chaves@bunge.com <mailto:anderson.chaves@bunge.com>
Documento Tomador
04341206427
Enviado em: 08/10/2026 18:56:38
Solicitação 2 de 2 — Maria Souza
⏳ Aguardando NF [ref NF-0190947310-02]
Enviado por: maria@x.com
Enviado em: 08/10/2026 19:01
E-mail gerado automaticamente pelo robô Solicitações NF. Código de envio: NF-0190947310"""


def test_le_as_solicitacoes_do_email_do_robo():
    p = ee.pedidos_do_robo(CORPO)
    assert [(x["nome"], x["email"], x["carimbo"], x["ref"]) for x in p] == [
        ("Nivaldo Anderson Chaves da Silva", "anderson.chaves@bunge.com", "08/10/2026 18:56:38", "NF-0190947310-01"),
        ("Maria Souza", "maria@x.com", "08/10/2026 19:01", "NF-0190947310-02")]


def test_aba_de_passagem_vai_e_volta():
    caixa = {"m1": {"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "assunto": "Solicitação NF - LAGOA",
                    "recebido": "2026-10-08T19:24:00", "lido": False, "pedidos": ee.pedidos_do_robo(CORPO)}}
    linhas = ee.linhas_pedidos(caixa, "PC1", datetime.datetime(2026, 10, 11, 9, 0))
    lidos = ee.ler_pedidos(linhas)
    assert lidos[0]["pc"] == "PC1" and not lidos[0]["lido"] and len(lidos[0]["pedidos"]) == 2
    assert ee.ler_pedidos([ee.CAB_PEDIDOS]) == []   # PC na versão nova, Caixa de Entrada sem solicitação


def sol(chave, email, data, carimbo):
    return {"chave": chave, "email": email, "emails": [], "data": data, "carimbo": carimbo, "hotel": "LAGOA"}


def test_liga_pelo_email_e_hora_do_formulario():
    s1 = sol("k1", "anderson.chaves@bunge.com", "2026-10-08", "10/8/2026 18:56:38")   # planilha no formato americano
    s2 = sol("k2", "anderson.chaves@bunge.com", "2026-09-01", "9/1/2026 10:00:00")    # outro pedido dele: fica de fora
    s3 = sol("k3", "maria@x.com", "2026-10-08", "08/10/2026 19:01:40")                 # "Enviado em" sem segundos
    caixas = {"PC1": [{"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-08T19:24:00", "lido": False,
                       "pedidos": ee.pedidos_do_robo(CORPO)},
                      {"id": "m2", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-09T08:00:00", "lido": True,
                       "pedidos": ee.pedidos_do_robo(CORPO)[:1]}]}   # o robô mandou o mesmo pedido de novo
    ligados, sem = dados.ligar_caixa([s1, s2, s3], caixas)
    assert set(ligados) == {"k1", "k3"} and sem == []
    assert ligados["k1"]["emails"] == 2 and ligados["k1"]["lido"] is False and ligados["k1"]["pc"] == "PC1"


def test_solicitacao_sem_formulario_aparece_com_aviso():
    caixas = {"PC1": [{"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-08T19:24:00", "lido": True,
                       "pedidos": ee.pedidos_do_robo(CORPO)[:1]}]}
    ligados, sem = dados.ligar_caixa([], caixas)
    assert ligados == {} and len(sem) == 1
    assert sem[0]["sem_formulario"] and sem[0]["nome"] == "Nivaldo Anderson Chaves da Silva" and sem[0]["na_caixa"]["pc"] == "PC1"
