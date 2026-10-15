"""Envio pelo PC dono da caixa do hotel (15/10/2026): o robô manda daqui só o que é caixa deste Outlook; caixa de
outro PC vai por pedido pela rede, e o PC dono manda da própria caixa do hotel para ela mesma. A conta do Ondina
(conta_remetente) não manda mais e-mail de hotel de outro PC."""
import urllib.error

import pytest

import envio_pc_dono as epd
from conftest import AGORA, ARACAJU, CABECALHO_HOTEL, Relogio
from main import executar
from modelos import EmailMontado


class LocalFalso:
    """O OutlookNF deste PC (só as caixas em `contas`)."""

    def __init__(self, contas=("notafiscal@estrela.com.br", "notafiscal@barra.com.br")):
        self.contas = {c: object() for c in contas}
        self.enviados, self.antigos, self.conexoes = [], set(), 0
        self.namespace = "NS"

    def conectar(self):
        self.conexoes += 1

    def enviar(self, email):
        self.enviados.append(email)

    def esta_nos_enviados(self, codigo, desde=None, destinatario=None):
        return codigo in self.antigos or any(e.codigo == codigo for e in self.enviados)

    def esta_na_caixa_saida(self, codigo, destinatario=None):
        return False


PCS = [{"pc": "PC-JOAO", "agente": "João", "contas_lista": ["notafiscal@estrela.com.br"], "online": True, "rede": "10.0.0.1:8766"},
       {"pc": "PC-CLARA", "agente": "Clara", "contas_lista": ["notafiscal@aracaju.com.br"], "online": True, "rede": "10.0.0.2:8766"},
       {"pc": "PC-BERNARDO", "agente": "Bernardo", "contas_lista": ["notafiscal@jeri.com.br"], "online": False, "rede": "10.0.0.3:8766"}]


class RedeFalsa:
    """O PC dono do outro lado (rede_local.perguntar)."""

    def __init__(self):
        self.pedidos, self.erro, self.mandados = [], None, set()

    def __call__(self, segredo, endereco, acao, corpo, tempo):
        self.pedidos.append((endereco, acao, corpo))
        if self.erro:
            raise self.erro
        if acao == "enviar":
            ja = corpo["codigo"] in self.mandados
            self.mandados.add(corpo["codigo"])
            return {"pc": "PC-CLARA", "conta": corpo["para"], "enviado": True, "ja_estava": ja}
        return {"pc": "PC-CLARA", "enviados": corpo["codigo"] in self.mandados, "saida": False}


def _email(para, codigo="NF-0123456789"):
    return EmailMontado(operador=para, destinatario=para, assunto="Solicitação NF",
                        html="<p>Código de envio: " + codigo + "</p>", codigo=codigo, solicitacoes=[])


def _outlook(local=None, rede=None, pcs=PCS, segredo=b"s"):
    return epd.OutlookComPcDono(local or LocalFalso(), lambda: pcs, segredo, este_pc="PC-JOAO", perguntar=rede or RedeFalsa())


def test_caixa_deste_outlook_sai_daqui_como_antes():
    local, rede = LocalFalso(), RedeFalsa()
    o = _outlook(local, rede)
    o.enviar(_email("notafiscal@estrela.com.br"))
    assert [e.destinatario for e in local.enviados] == ["notafiscal@estrela.com.br"] and rede.pedidos == []


def test_caixa_de_outro_pc_vai_pro_pc_dono_e_ele_confere():
    local, rede = LocalFalso(), RedeFalsa()
    o = _outlook(local, rede)
    o.enviar(_email("NotaFiscal@Aracaju.com.br"))
    assert local.enviados == []                                   # nada pela conta do Ondina
    (end, acao, corpo), = rede.pedidos
    assert end == "10.0.0.2:8766" and acao == "enviar"
    assert corpo["para"] == "notafiscal@aracaju.com.br" and corpo["codigo"] == "NF-0123456789" and "Código" in corpo["html"]
    assert o.esta_nos_enviados("NF-0123456789", None, destinatario="notafiscal@aracaju.com.br") is True
    assert rede.pedidos[-1][1] == "conferir_envio"


def test_pc_dono_desligado_nao_manda_pelo_ondina():
    local, rede = LocalFalso(), RedeFalsa()
    with pytest.raises(epd.NaoEnviado, match="desligado"):
        _outlook(local, rede).enviar(_email("notafiscal@jeri.com.br"))
    assert local.enviados == [] and rede.pedidos == []


def test_caixa_de_nenhum_pc_sai_pela_conta_remetente():
    local, rede = LocalFalso(), RedeFalsa()
    _outlook(local, rede).enviar(_email("teste@x.com"))           # e-mail de teste do modo TESTE
    assert [e.destinatario for e in local.enviados] == ["teste@x.com"] and rede.pedidos == []


def test_pedido_que_nem_chegou_e_nao_enviado_e_o_pc_fica_de_fora_na_volta():
    rede = RedeFalsa()
    rede.erro = urllib.error.URLError(ConnectionRefusedError("recusada"))
    o = _outlook(rede=rede)
    with pytest.raises(epd.NaoEnviado, match="não respondeu"):
        o.enviar(_email("notafiscal@aracaju.com.br"))
    with pytest.raises(epd.NaoEnviado, match="desligado ou sem rede"):
        o.enviar(_email("notafiscal@aracaju.com.br", "NF-ABCDEF0123"))
    assert len(rede.pedidos) == 1


def test_pc_dono_ainda_sem_a_versao_nova_e_nao_enviado():
    rede = RedeFalsa()
    rede.erro = urllib.error.HTTPError("http://x/rede/enviar", 404, "não encontrado", {}, None)
    with pytest.raises(epd.NaoEnviado, match="versão nova"):
        _outlook(rede=rede).enviar(_email("notafiscal@aracaju.com.br"))


def test_resposta_que_demorou_nao_e_certeza_de_nao_enviado():
    rede = RedeFalsa()
    rede.erro = TimeoutError("timed out")
    with pytest.raises(TimeoutError):
        _outlook(rede=rede).enviar(_email("notafiscal@aracaju.com.br"))


def test_conferencia_acha_o_que_saiu_pelo_ondina_antes_e_pc_fora_nao_vira_falso():
    local, rede = LocalFalso(), RedeFalsa()
    local.antigos.add("NF-AAAAAAAAAA")
    o = _outlook(local, rede)
    assert o.esta_nos_enviados("NF-AAAAAAAAAA", None, destinatario="notafiscal@aracaju.com.br") is True
    assert rede.pedidos == []
    with pytest.raises(RuntimeError):   # PC dono desligado: "não sei" (o main.py segura), nunca "não saiu"
        o.esta_nos_enviados("NF-BBBBBBBBBB", None, destinatario="notafiscal@jeri.com.br")


def test_no_robo_pc_dono_desligado_deixa_a_linha_pendente_e_tira_do_diario(cfg, planilha, monkeypatch):
    cfg["destino_envio"] = "hotel"
    for aba in list(planilha.planilhas["PLANILHA_CENTRAL"]):
        if aba.endswith("(respostas)") and aba != ARACAJU:
            del planilha.planilhas["PLANILHA_CENTRAL"][aba]
    local = LocalFalso()
    pcs = [{**PCS[1], "online": False}]
    o = epd.OutlookComPcDono(local, lambda: pcs, b"s", este_pc="PC-JOAO", perguntar=RedeFalsa())
    relogio = Relogio()
    assert executar(cfg, planilha, o, esperar=relogio.esperar, agora=AGORA, relogio=relogio.agora) == 1
    i = CABECALHO_HOTEL.index("Enviado")
    assert [l[i] for l in planilha.aba(ARACAJU)[1:]] == ["FALSE"]   # continua pendente: vai na próxima volta
    assert local.enviados == []
    import main
    from diario_envios import DiarioEnvios
    assert DiarioEnvios(main.PASTA_ESTADO / "envios_pendentes.json").listar() == []


# ---------- no PC dono ----------
class Item:
    def __init__(self, corpo=""):
        self.Body, self.HTMLBody = corpo, ""


class Itens(list):
    def Sort(self, *_):
        pass


class Pasta:
    def __init__(self):
        self.Items = Itens()


class Loja:
    def __init__(self):
        self.pastas = {4: Pasta(), 5: Pasta()}

    def GetDefaultFolder(self, tipo):
        return self.pastas[tipo]


class Conta:
    def __init__(self, smtp):
        self.SmtpAddress, self.DeliveryStore = smtp, Loja()


class Ole:
    def __init__(self, mail):
        self.mail = mail

    def Invoke(self, dispid, _lcid, _flags, _ret, conta):
        assert dispid == epd.DISPID_SEND_USING_ACCOUNT
        self.mail.conta = conta


class Mail:
    def __init__(self, app):
        self.app, self.conta, self.To, self.Subject, self.HTMLBody = app, None, "", "", ""
        self._oleobj_ = Ole(self)

    def Send(self):
        self.app.saidos.append(self)
        self.conta.DeliveryStore.pastas[5].Items.append(Item(self.HTMLBody))


class App:
    def __init__(self):
        self.saidos = []

    def CreateItem(self, _tipo):
        return Mail(self)


class Ns:
    def __init__(self, contas):
        self.Accounts, self.padrao = contas, Loja()

    def GetDefaultFolder(self, tipo):   # a caixa padrão do Outlook (às vezes a cópia do enviado vai pra lá)
        return self.padrao.GetDefaultFolder(tipo)

    def SendAndReceive(self, _):
        pass


CAIXAS = {"notafiscal@aracaju.com.br": "ARACAJU", "notafiscal@jeri.com.br": "JERI"}


def test_pc_dono_manda_da_caixa_do_hotel_para_ela_mesma_e_nao_repete():
    conta = Conta("NotaFiscal@aracaju.com.br")
    app, ns = App(), Ns([Conta("pessoal@x.com"), conta])
    corpo = {"codigo": "NF-0123456789", "para": "notafiscal@aracaju.com.br", "assunto": "Solicitação NF",
             "html": "<p>Código de envio: NF-0123456789</p>"}
    r = epd.enviar_aqui(app, ns, corpo, CAIXAS)
    assert r["enviado"] and not r["ja_estava"]
    (mail,) = app.saidos
    assert mail.To == "notafiscal@aracaju.com.br" and mail.conta is conta and mail.Subject == "Solicitação NF"
    assert epd.enviar_aqui(app, ns, corpo, CAIXAS)["ja_estava"] and len(app.saidos) == 1   # pedido repetido
    assert epd.conferir_aqui(ns, corpo, CAIXAS) == {"pc": r["pc"], "conta": "notafiscal@aracaju.com.br",
                                                    "enviados": True, "saida": False}


def test_pc_dono_recusa_caixa_que_nao_tem_caixa_pessoal_e_pedido_sem_codigo():
    app, ns = App(), Ns([Conta("notafiscal@aracaju.com.br"), Conta("pessoal@x.com")])
    base = {"codigo": "NF-0123456789", "assunto": "x", "html": "<p>x</p>"}
    with pytest.raises(PermissionError, match="não está no Outlook"):
        epd.enviar_aqui(app, ns, {**base, "para": "notafiscal@jeri.com.br"}, CAIXAS)
    with pytest.raises(PermissionError, match="não é caixa de hotel"):
        epd.enviar_aqui(app, ns, {**base, "para": "pessoal@x.com"}, CAIXAS)
    with pytest.raises(PermissionError, match="código"):
        epd.enviar_aqui(app, ns, {**base, "para": "notafiscal@aracaju.com.br", "codigo": "qualquer"}, CAIXAS)
    assert app.saidos == []


def test_copia_do_enviado_na_caixa_padrao_tambem_conta():
    conta = Conta("notafiscal@aracaju.com.br")
    ns = Ns([conta])
    ns.padrao.pastas[5].Items.append(Item("... Código de envio: NF-0123456789"))
    corpo = {"codigo": "NF-0123456789", "para": "notafiscal@aracaju.com.br", "assunto": "x", "html": "<p>x</p>"}
    assert epd.conferir_aqui(ns, corpo, CAIXAS)["enviados"] is True
    app = App()
    assert epd.enviar_aqui(app, ns, corpo, CAIXAS)["ja_estava"] and app.saidos == []

