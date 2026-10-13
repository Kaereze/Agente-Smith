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
