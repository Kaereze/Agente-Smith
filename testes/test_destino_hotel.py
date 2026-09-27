"""destino_envio = "hotel": cada hotel recebe as solicitações dele no e-mail da coluna B do Cadastro_Hoteis."""
from conftest import AGORA, CENTRAL, Relogio
from main import executar
from outlook import OutlookNF
from sheets import ler_hoteis


def test_cada_hotel_vai_pro_proprio_email(cfg, planilha):
    cfg["destino_envio"] = "hotel"
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert erros == []
    assert {h.nome: h.operador for h in hoteis} == {
        "ESTRELA CENTRO": "notafiscal@estrela.com.br", "ARACAJU": "notafiscal@aracaju.com.br",
        "BARRA": "notafiscal@barra.com.br"}


def test_hotel_sem_email_no_cadastro_vira_erro(cfg, planilha):
    cfg["destino_envio"] = "hotel"
    planilha.planilhas[CENTRAL]["Cadastro_Hoteis"][1][1] = ""   # ARACAJU sem e-mail
    hoteis, erros = ler_hoteis(planilha, cfg)
    assert "ARACAJU" not in {h.nome for h in hoteis} and any("ARACAJU" in e for e in erros)


def test_envio_por_hotel_manda_um_email_por_hotel(cfg, planilha, outlook):
    cfg["destino_envio"] = "hotel"
    relogio = Relogio()
    assert executar(cfg, planilha, outlook, agora=AGORA, esperar=relogio.esperar, relogio=relogio.agora) == 0
    assert sorted(e.destinatario for e in outlook.enviados) == [
        "notafiscal@aracaju.com.br", "notafiscal@barra.com.br", "notafiscal@estrela.com.br"]


class _Conta:
    def __init__(self, smtp):
        self.SmtpAddress = smtp


def test_sai_da_propria_caixa_do_hotel_quando_ela_esta_no_outlook():
    o = OutlookNF({"conta_remetente": "ondina@x.com"})
    o.conta = _Conta("ondina@x.com")
    hotel = _Conta("notafiscal@luxor.com.br")
    o.contas = {"ondina@x.com": o.conta, "notafiscal@luxor.com.br": hotel}
    assert o.conta_para("NotaFiscal@Luxor.com.br") is hotel          # a própria caixa do hotel
    assert o.conta_para("notafiscal@barra.com.br") is o.conta         # caixa fora deste PC: sai da Ondina


class _ContaCOM:
    """Igual à conta de verdade do Outlook: NÃO pode ser chave de dict (CDispatch)."""
    __hash__ = None

    def __init__(self, smtp, itens):
        self.SmtpAddress = smtp
        self.DeliveryStore = self
        self._itens = itens

    def GetDefaultFolder(self, tipo):
        return self

    @property
    def Items(self):
        return _Itens(self._itens)


class _Itens(list):
    def Sort(self, *a):
        pass


class _Item:
    def __init__(self, corpo):
        self.Body, self.HTMLBody = corpo, corpo


def test_confirma_envio_na_caixa_do_hotel_com_conta_de_verdade():
    """Caso real 24/09: a confirmação quebrou com 'unhashable type: CDispatch' e os 29 ficaram sem TRUE."""
    o = OutlookNF({"conta_remetente": "ondina@x.com"})
    o.conta = _ContaCOM("ondina@x.com", [_Item("rodapé NF-AAAAAAAAAA")])
    hotel = _ContaCOM("notafiscal@luxor.com.br", [_Item("rodapé NF-BBBBBBBBBB")])
    o.contas = {"ondina@x.com": o.conta, "notafiscal@luxor.com.br": hotel}
    assert o.esta_nos_enviados("NF-BBBBBBBBBB", destinatario="notafiscal@luxor.com.br")   # na caixa do hotel
    assert o.esta_nos_enviados("NF-AAAAAAAAAA", destinatario="notafiscal@barra.com.br")   # saiu pela Ondina
    assert not o.esta_nos_enviados("NF-CCCCCCCCCC", destinatario="notafiscal@luxor.com.br")
    assert not o.esta_na_caixa_saida("NF-BBBBBBBBBB", destinatario="ondina@x.com")
