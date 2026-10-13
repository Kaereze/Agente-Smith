"""Novo e-mail na Caixa de entrada (13/10/2026): sai da caixa do hotel, sem anexo obrigatório, sem marcar NF."""
import datetime

import pytest

import app_servidor
import envio_nf


def _estado(monkeypatch, contas):
    e = object.__new__(app_servidor.Estado)
    pedidos = []

    class Envio:
        def pedir(self, *args, **kw):
            pedidos.append((args, kw))
            return {"ok": True, "id": "x1", "destino": "PC1"}

    e.envio_nf = Envio()
    monkeypatch.setattr(app_servidor.Estado, "contas_de_hotel", lambda self: contas)
    return e, pedidos


CONTAS = [{"conta": "notafiscal@redeandradeondina.com.br", "hotel": "ONDINA", "agente": "João", "pc": "PC1", "online": True}]


def test_novo_email_sai_livre_e_sem_ligar_a_solicitacao(monkeypatch):
    e, pedidos = _estado(monkeypatch, CONTAS)
    r = e.enviar_email_novo({"conta_de": "notafiscal@redeandradeondina.com.br", "para": "hospede@exemplo.com",
                             "assunto": "Solicitação de dados", "corpo": "Bom dia!\nCPF do hóspede:"}, "João")
    assert r["ok"]
    args, kw = pedidos[0]
    sol = args[0]
    assert sol["aba"] == "" and sol["carimbo"] == ""          # não marca NF em nenhuma solicitação
    assert kw.get("livre") is True and args[4] == []          # sem anexo obrigatório


@pytest.mark.parametrize("corpo, erro", [
    ({"conta_de": "outra@x.com", "para": "h@x.com", "assunto": "a", "corpo": "b"}, "caixa do hotel"),
    ({"conta_de": "notafiscal@redeandradeondina.com.br", "para": "sem-arroba", "assunto": "a", "corpo": "b"}, "destinatário"),
    ({"conta_de": "notafiscal@redeandradeondina.com.br", "para": "h@x.com", "assunto": "a", "corpo": "  "}, "mensagem"),
])
def test_novo_email_valida_campos(monkeypatch, corpo, erro):
    e, pedidos = _estado(monkeypatch, CONTAS)
    with pytest.raises(ValueError, match=erro):
        e.enviar_email_novo(corpo, "João")
    assert pedidos == []


def test_pedir_aceita_email_livre_sem_anexo_e_usa_a_mensagem_escrita():
    s = object.__new__(envio_nf.ServicoEnvio)
    linhas = []

    class Backend:
        def anexar_linhas(self, planilha, aba, novas):
            linhas.extend(novas)

    s.backend, s.central, s.pc, s.fila, s.cfg, s.contas = Backend(), "C", "PC1", {}, {}, []
    s.relogio = lambda: datetime.datetime(2026, 10, 13, 9, 0)
    s.destino_para = lambda conta, aceitar_desligado=False: ("PC2", "")   # outro PC: só entra na fila
    sol = {"aba": "", "carimbo": "", "email": "h@x.com", "hotel": "ONDINA", "nome": "h@x.com"}
    assert s.pedir(sol, "h@x.com", "a", "notafiscal@x.com", [], "João", "texto")["ok"] is False   # NF continua exigindo anexo
    r = s.pedir(sol, "h@x.com", "Solicitação de dados", "notafiscal@x.com", [], "João", "Bom dia!", livre=True)
    assert r["ok"] and r["destino"] == "PC2"
    assert "Bom dia!" in str(linhas[-1])


def test_encaminhar_leva_a_assinatura_padrao(monkeypatch):
    # 13/10/2026: assinatura padrão em todo tipo de envio, inclusive encaminhar (e no campo certo, não no Cc)
    e, pedidos = _estado(monkeypatch, CONTAS)
    monkeypatch.setattr(app_servidor.Estado, "_email", lambda self, i: {"id": i, "assunto": "Nota", "de": "h@x.com",
                                                                        "hotel": "ONDINA", "nome": "H", "caixa": CONTAS[0]["conta"]})
    monkeypatch.setattr(app_servidor.envio_nf, "caminho_selo", lambda s: "joao.png" if s == "joao" else None)
    e.encaminhar_email({"id": "e1", "para": "outro@x.com", "corpo": "Prezado(a) hóspede,", "selo": "joao"}, "João")
    args, kw = pedidos[0]
    assert kw.get("selo") == "joao" and len(args) == 7          # selo pelo nome; cc não recebe a assinatura
    assert kw.get("acao") == app_servidor.envio_nf.ENCAMINHAR


def test_tira_a_assinatura_automatica_do_outlook():
    # 13/10/2026: Reply()/Forward() já vinham com a assinatura padrão da caixa; somada à do Painel, saíam duas
    html = ("<html><body><p class=MsoNormal><o:p>&nbsp;</o:p></p>"
            "<p class=MsoNormal><a name=\"_MailAutoSig\">Prezado(a) hóspede,</a></p>"
            "<p class=MsoNormal>Atenciosamente,<img src=\"cid:image001.png@01DC5E2A.1\"></p>"
            "<div style='border:none;border-top:solid #E1E1E1 1.0pt;padding:3.0pt 0cm 0cm 0cm'>"
            "<p><b>De:</b> hospede@x.com</p></div><p>texto original do hóspede</p></body></html>")
    limpo, cids = envio_nf.tirar_assinatura_automatica(html)
    assert "Prezado(a) hóspede" not in limpo and "image001" not in limpo
    assert "texto original do hóspede" in limpo and "De:" in limpo       # o histórico continua
    assert cids == {"image001.png@01dc5e2a.1"}
    assert envio_nf.tirar_assinatura_automatica("<p>sem assinatura</p>") == ("<p>sem assinatura</p>", set())


def test_espelho_mostra_se_o_enviado_saiu_pelo_painel():
    import espelho_emails as ee
    agora = datetime.datetime(2026, 10, 13, 11, 0)
    itens = {"a": {"id": "a", "pasta": ee.ENVIADO, "caixa": "c", "hotel": "VERNON", "de": "c", "para": "h@x.com",
                   "assunto": "NF", "quando": "2026-10-13T10:00:00", "via": "painel"}}
    linhas = ee.linhas_da_aba(itens, {}, "PC1", agora)
    assert len(linhas[1]) == len(ee.CABECALHO)
    assert ee.ler_aba(linhas)[0]["via"] == "painel"
