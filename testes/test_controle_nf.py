"""Regras do ✅ / 💬 (controle_nf.py) — sem Outlook."""
import datetime

from conftest import CABECALHO_HOTEL, linha_hotel
from controle_nf import (Registro, abrir_registro, assunto_com_contador, categorias_atualizadas, ler_assunto_nf,
                         paragrafo_status, situacao, tem_anexo_nf, trocar_paragrafo_status)
from main import executar
from modelos import Hotel
from montar_email import montar_emails
from sheets import interpretar_aba

EXT = ["pdf", "xml", "zip"]
DIA = datetime.datetime(2026, 9, 24, 14, 30)


def _sol(ref="NF-A-01", emails=("hospede@x.com",), nomes=("Maria Débora Souza",), partes=1,
         data="2026-09-22", email_hotel="notafiscal@royal.com.br"):
    return {"codigo": ref.rsplit("-", 1)[0], "hotel": "ROYAL", "aba": "x", "email_hotel": email_hotel,
            "carimbo": "", "data_pedido": data, "nome": nomes[0], "emails": list(emails), "nomes": list(nomes),
            "partes": partes, "nfs": {}, "tratativas": {}}


def _registro(*sols):
    r = Registro()
    for s in sols:
        ref = s.pop("_ref", "NF-A-01")
        r.solicitacoes[ref] = s
        r.emails.setdefault(s["codigo"], {"destinatario": "op@x", "assunto": "", "refs": [],
                                          "precisa_atualizar": False})["refs"].append(ref)
    return r


def _envio(assunto, para=("hospede@x.com",), anexos=("NF 1212.pdf",), entry="E1", conta="notafiscal@royal.com.br",
           data=DIA):
    return {"entry_id": entry, "conta": conta, "destinatarios": set(para), "assunto": assunto,
            "data": data, "anexos": list(anexos)}


def test_le_assunto_de_nf():
    assert ler_assunto_nf("NF 1212 - MARIA DÉBORA") == ("1212", "MARIA DÉBORA")
    assert ler_assunto_nf("NF 1812 - FABIANO DA LUZ - 363305") == ("1812", "FABIANO DA LUZ")
    assert ler_assunto_nf("RES: NF-1212 - Maria") == ("1212", "Maria")
    assert ler_assunto_nf("NFe 77 - Ana") == ("77", "Ana")
    assert ler_assunto_nf("Dúvida sobre a NF 1212") is None
    assert ler_assunto_nf("NF 1212") is None


def test_imagem_da_assinatura_nao_conta_como_anexo():
    assert not tem_anexo_nf(["image001.png", "logo.jpg"], EXT)
    assert tem_anexo_nf(["image001.png", "NF 1212.PDF"], EXT)


def test_nf_com_anexo_vira_check():
    r = _registro(_sol())
    assert r.aplicar_envio(_envio("NF 1212 - MARIA DEBORA"), EXT) == ("NF-A-01", "nf")
    tipo, texto = situacao(r.solicitacoes["NF-A-01"])
    assert tipo == "ok" and "1212" in texto
    assert r.emails["NF-A"]["precisa_atualizar"] is True


def test_nf_sem_anexo_ou_outro_assunto_vira_tratativa():
    r = _registro(_sol())
    assert r.aplicar_envio(_envio("NF 1212 - MARIA", anexos=()), EXT)[1] == "tratativa"
    assert r.aplicar_envio(_envio("Precisamos do CNPJ correto", entry="E2", anexos=()), EXT)[1] == "tratativa"
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "tratativa"
    # depois chega a NF: vira ✅ (a tratativa não segura o check)
    r.aplicar_envio(_envio("NF 1300 - MARIA", entry="E3"), EXT)
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "ok"


def test_nota_dividida_espera_todas():
    r = _registro(_sol(partes=2))
    r.aplicar_envio(_envio("NF 1212 - MARIA"), EXT)
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "parcial"
    r.aplicar_envio(_envio("NF 1212 - MARIA", entry="E2"), EXT)      # reenvio da MESMA nota
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "parcial"
    r.aplicar_envio(_envio("NF 1213 - MARIA", entry="E3"), EXT)
    assert situacao(r.solicitacoes["NF-A-01"])[0] == "ok"


def test_enviou_pra_outro_email_casa_pelo_nome_no_mesmo_hotel():
    r = _registro(_sol())
    assert r.aplicar_envio(_envio("NF 1212 - MARIA DEBORA", para=("financeiro@empresa.com",)), EXT)[1] == "nf"
    # mesmo nome, mas NF saiu de OUTRO hotel: não mistura
    r2 = _registro(_sol())
    assert r2.aplicar_envio(_envio("NF 9 - MARIA DEBORA", para=("x@y.com",), conta="notafiscal@outro.com.br"),
                            EXT) is None


def test_nome_ambiguo_nao_marca_nada():
    a, b = _sol(nomes=("Maria Souza",)), _sol(nomes=("Maria Souza Lima",), emails=("outra@x.com",))
    b["_ref"] = "NF-A-02"
    r = _registro(a, b)
    assert r.aplicar_envio(_envio("NF 1 - MARIA SOUZA", para=("z@z.com",)), EXT) is None


def test_mesmo_email_enviado_nao_conta_duas_vezes_e_envio_antigo_e_ignorado():
    r = _registro(_sol(partes=2))
    r.aplicar_envio(_envio("NF 1 - MARIA"), EXT)
    assert r.aplicar_envio(_envio("NF 1 - MARIA"), EXT) is None                      # mesmo EntryID
    antigo = _envio("NF 2 - MARIA", entry="E9", data=datetime.datetime(2026, 9, 1))  # antes do pedido
    assert r.aplicar_envio(antigo, EXT) is None


def test_email_que_nao_e_de_hospede_e_ignorado():
    r = _registro(_sol())
    assert r.aplicar_envio(_envio("Relatório do dia", para=("gerente@andradehoteis.com.br",)), EXT) is None


def test_troca_o_selo_mesmo_com_html_reescrito_pelo_outlook():
    sol = _sol()
    original = "<div>" + paragrafo_status("NF-A-01", sol) + "<table></table></div>"
    # o Outlook costuma reescrever assim o que recebe:
    reescrito = ('<div><p class=MsoNormal style="margin:0"><span style="background:#8a7a4f">⏳ Aguardando NF</span>'
                 '<span style="font-size:7.5pt"> [ref NF-A-01]</span><o:p></o:p></p><table></table></div>')
    sol["nfs"]["1212"] = {"data": "2026-09-24T14:30:00", "assunto": "NF 1212 - M", "entry_id": "E1"}
    for corpo in (original, reescrito):
        novo, achou = trocar_paragrafo_status(corpo, "NF-A-01", paragrafo_status("NF-A-01", sol))
        assert achou and "✅ NF enviada" in novo and "Aguardando" not in novo
        assert novo.count("[ref NF-A-01]") == 1 and novo.endswith("<table></table></div>")


def test_assunto_e_categorias():
    a = assunto_com_contador("Solicitações NF (24) - ROYAL", 3, 24)
    assert a == "[3/24 ✅] Solicitações NF (24) - ROYAL"
    assert assunto_com_contador(a, 24, 24) == "[24/24 ✅] Solicitações NF (24) - ROYAL"
    assert categorias_atualizadas("Urgente, ⏳ NF pendente", 2, 5, True) == "Urgente, ⏳ NF pendente, 💬 Tratativa"
    assert categorias_atualizadas("Urgente, ⏳ NF pendente, 💬 Tratativa", 5, 5, True) == "Urgente, ✅ NF concluído"


def test_email_consolidado_sai_com_ref_e_selo_de_aguardando(cfg):
    hotel = Hotel("aba", "ROYAL", "op@x", "P", "notafiscal@royal.com.br")
    linha = linha_hotel(1)
    pend, _ = interpretar_aba(hotel, [CABECALHO_HOTEL, linha], cfg)
    [email] = montar_emails(pend, cfg)
    s = email.solicitacoes[0]
    assert s.ref == f"{email.codigo}-01" and f"[ref {s.ref}]" in email.html
    assert "⏳ Aguardando NF" in email.html
    assert s.emails_contato == ["hospede1@x.com"] and s.data_pedido == "2026-09-02"


def test_nota_dividida_lida_do_formulario(cfg):
    cab = ["Carimbo de data/hora", "E-mail", "Nome Tomador", "Nota Dividida", "Dividida em quantas vezes", "Enviado"]
    pend, _ = interpretar_aba(Hotel("a", "H", "o@x", "P"), [cab, ["9/2/2026", "a@x.com", "Ana", "Sim", "3", ""],
                                                           ["9/2/2026", "b@x.com", "Bia", "Não", "", ""]], cfg)
    assert [s.partes_esperadas for s in pend] == [3, 1]
    assert pend[0].nomes == ["Ana"]


def test_robo_de_envio_anota_no_registro(cfg, planilha, outlook, pastas_temporarias):
    assert executar(cfg, planilha, outlook, esperar=lambda s: None) == 0
    with abrir_registro(pastas_temporarias / "estado" / "controle_nf.json") as r:
        assert len(r.emails) == 2 and len(r.solicitacoes) == 4
        assert {e.codigo for e in outlook.enviados} == set(r.emails)


def test_mesma_solicitacao_em_dois_emails_fica_igual_nos_dois():
    from controle_nf import Registro
    base = {"aba": "A", "carimbo": "25/09/2026 20:34:48", "emails": ["x@y.com"], "tratativas": {}}
    reg = Registro({"solicitacoes": {"NF-1-01": {**base, "codigo": "NF-1", "nfs": {"1201": {"data": "2026-09-27T13:54"}}},
                                     "NF-2-01": {**base, "codigo": "NF-2", "nfs": {}}},
                    "emails": {"NF-1": {"refs": ["NF-1-01"]}, "NF-2": {"refs": ["NF-2-01"]}}})
    assert reg.igualar_gemeas() == 1
    assert "1201" in reg.solicitacoes["NF-2-01"]["nfs"] and reg.emails["NF-2"]["precisa_atualizar"]
