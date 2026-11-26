"""Relatório do Mail Analytics pedido pelo notebook administrador e enviado pelo Outlook do PC principal, pela conta do
CECOMTUR (26/11/2026). Quem recebe são os chefes que o notebook manda."""
import base64

import pytest

from emails import envio_relatorio as er


class Conta:
    def __init__(self, smtp):
        self.SmtpAddress = smtp


class Ole:
    def __init__(self, mail):
        self.mail = mail

    def Invoke(self, dispid, _lcid, _flags, _ret, conta):
        assert dispid == er.DISPID_SEND_USING_ACCOUNT
        self.mail.conta = conta


class MailFalso:
    def __init__(self, enviados):
        self.To = self.CC = self.Subject = self.HTMLBody = ""
        self.conta, self.anexos, self._enviados = None, [], enviados
        self.Attachments = self
        self._oleobj_ = Ole(self)

    def Add(self, caminho):
        with open(caminho, "rb") as f:
            self.anexos.append((caminho.replace("\\", "/").rsplit("/", 1)[-1], f.read()))

    def Send(self):
        self._enviados.append(self)


class AppFalso:
    def __init__(self, contas=("joao@rede.com.br", "reservas@cecomtur.com.br", "notafiscal@hotel.com.br")):
        self.enviados = []
        self.Accounts = [Conta(c) for c in contas]

    def GetNamespace(self, _nome):
        return self

    def CreateItem(self, _tipo):
        return MailFalso(self.enviados)


def _pedido(**extra):
    p = {"id": "MA-" + "a" * 32, "para": ["Chefe@rede.com.br"], "cc": ["copia@rede.com.br"],
         "assunto": "Relatório", "html": "<p>oi</p>", "anexos": []}
    p.update(extra)
    return p


@pytest.fixture(autouse=True)
def feitos_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(er, "_caminho_feitos", lambda: tmp_path / "feitos.json")


def test_envia_aos_chefes_do_notebook_pela_conta_do_cecomtur():
    app = AppFalso()
    r = er.enviar_aqui(app, _pedido(), set())
    assert r["enviado"] and not r["ja_estava"] and r["conta"] == "reservas@cecomtur.com.br"
    m = app.enviados[0]
    assert (m.To, m.CC, m.Subject, m.HTMLBody) == ("chefe@rede.com.br", "copia@rede.com.br", "Relatório", "<p>oi</p>")
    assert m.conta.SmtpAddress == "reservas@cecomtur.com.br"


def test_conta_exata_pedida_pelo_notebook():
    app = AppFalso(contas=("a@cecomtur.com.br", "b@cecomtur.com.br"))
    er.enviar_aqui(app, _pedido(conta_de="B@cecomtur.com.br"), set())
    assert app.enviados[0].conta.SmtpAddress == "b@cecomtur.com.br"


def test_sem_conta_do_cecomtur_ou_ambigua_nao_envia():
    for contas in (("joao@rede.com.br",), ("a@cecomtur.com.br", "b@cecomtur.com.br")):
        app = AppFalso(contas=contas)
        with pytest.raises(PermissionError):
            er.enviar_aqui(app, _pedido(), set())
        assert app.enviados == []


def test_pedido_repetido_nao_envia_de_novo():
    app = AppFalso()
    er.enviar_aqui(app, _pedido(), set())
    r = er.enviar_aqui(app, _pedido(), set())
    assert r["ja_estava"] and len(app.enviados) == 1


def test_lista_opcional_do_config_local_restringe():
    cfg = {"relatorio_pela_rede": {"destinatarios_permitidos": ["Chefe@rede.com.br", "copia@rede.com.br"]}}
    permitidos = er.destinatarios_permitidos(cfg)
    assert permitidos == {"chefe@rede.com.br", "copia@rede.com.br"}
    er.enviar_aqui(AppFalso(), _pedido(), permitidos)
    with pytest.raises(PermissionError, match="destinatarios_permitidos"):
        er.enviar_aqui(AppFalso(), _pedido(id="MA-" + "c" * 32, cc=["estranho@fora.com"]), permitidos)
    assert er.destinatarios_permitidos({}) == set()


def test_recusa_sem_id_sem_texto_e_destinatarios_demais():
    muitos = [f"p{i}@x.com" for i in range(er.MAX_DESTINATARIOS + 1)]
    for pedido in (_pedido(id="x"), _pedido(html=" "), _pedido(para=[]), _pedido(para=muitos), _pedido(para=["nao-email"])):
        with pytest.raises(PermissionError):
            er.enviar_aqui(AppFalso(), pedido, set())


def test_anexo_vai_junto_e_tipo_perigoso_e_recusado():
    app = AppFalso()
    anexo = {"nome": "..\\..\\dashboard.html", "base64": base64.b64encode(b"<html/>").decode()}
    er.enviar_aqui(app, _pedido(anexos=[anexo]), set())
    assert app.enviados[0].anexos == [("dashboard.html", b"<html/>")]
    with pytest.raises(PermissionError, match="tipo de anexo"):
        er.enviar_aqui(AppFalso(), _pedido(id="MA-" + "b" * 32, anexos=[{"nome": "x.exe", "base64": ""}]), set())


def test_so_o_principal_atende():
    from painel.estado_rede import RedeMixin

    class E(RedeMixin):
        cfg = {"papel": "conferente"}
    with pytest.raises(PermissionError, match="só o PC principal"):
        E().rede_enviar_relatorio(_pedido())
    E.cfg = {"papel": "so_painel"}
    with pytest.raises(PermissionError):
        E().rede_enviar_relatorio(_pedido())
