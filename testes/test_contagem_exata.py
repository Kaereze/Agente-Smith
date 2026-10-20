"""Caixa de Entrada contada exatamente (usuário, 20/10/2026: "precisam ser contabilizados exatamente o que tiver na caixa
de entrada de cada email cadastrado").

No PC do João, 9 de 55 e-mails ficavam de fora: as caixas são POP3 e o e-mail cai no Outlook 10-20 min depois da hora
do servidor (ReceivedTime), maior que a folga da volta. Agora a volta procura pela hora em que o e-mail caiu/mudou no
Outlook e, no fim, confere o total de cada caixa; diferente, relê aquela caixa inteira.
"""
import datetime
import re

import espelho_emails as ee
from test_espelho_emails import Central, Item, Lista, OutlookFalso

D = datetime.datetime


class ListaComFiltro(Lista):
    """Como o Outlook: Restrict de verdade em [Campo] >= 'dd/mm/aaaa hh:mm'."""
    def Restrict(self, filtro):
        m = re.match(r"\[(\w+)\] >= '(\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d)'", filtro)
        campo, desde = m.group(1), D(int(m.group(4)), int(m.group(3)), int(m.group(2)), int(m.group(5)), int(m.group(6)))
        return ListaComFiltro(i for i in self if getattr(i, campo, None) and getattr(i, campo) >= desde)


def _montar(tmp_path, monkeypatch):
    monkeypatch.setattr(ee, "CAMINHO_ESTADO", tmp_path / "espelho.json")
    monkeypatch.setattr(ee.socket, "gethostname", lambda: "PC-A")
    ol = OutlookFalso("nf@luxor.com")
    ol.entrada.Items, ol.enviados.Items = ListaComFiltro(), ListaComFiltro()
    cfg = {"planilha_central_id": "C", "aba_cadastro_hoteis": "Cadastro_Hoteis", "conta_remetente": "robo@rede.com"}
    agora = [D(2026, 10, 20, 10, 0)]
    return ol, ee.Espelho(Central(), cfg, relogio=lambda: agora[0]), agora


def _item(eid, servidor, caiu):
    it = Item(eid, "hospede@gmail.com", "Nota fiscal", "Preciso da nota", servidor)
    it.LastModificationTime, it.CreationTime = caiu, caiu
    return it


def _na_entrada(esp):
    return sorted(e["id"] for e in esp.itens.values() if e["pasta"] == "entrada")


def test_email_pop3_que_cai_no_outlook_depois_entra_na_hora(tmp_path, monkeypatch):
    ol, esp, agora = _montar(tmp_path, monkeypatch)
    ol.receber(_item("E1", D(2026, 10, 20, 9, 0), D(2026, 10, 20, 9, 1)))
    esp.volta(ol)   # 10:00, volta completa
    agora[0] = D(2026, 10, 20, 10, 30)
    esp.volta(ol)   # 10:30
    # chegou ao servidor às 10:05 e só caiu no Outlook às 10:31 (a hora do servidor é antes da folga da volta)
    ol.receber(_item("E2", D(2026, 10, 20, 10, 5), D(2026, 10, 20, 10, 31)))
    agora[0] = D(2026, 10, 20, 10, 32)
    esp.volta(ol)
    assert _na_entrada(esp) == sorted([ee.id_do_email("E1"), ee.id_do_email("E2")])
    assert esp.contagem["nf@luxor.com"] == [2, 2]


def test_contagem_diferente_rele_a_caixa_inteira(tmp_path, monkeypatch):
    ol, esp, agora = _montar(tmp_path, monkeypatch)
    for n in range(3):
        ol.receber(_item(f"E{n}", D(2026, 10, 20, 8, n), D(2026, 10, 20, 8, n)))
    esp.volta(ol)
    assert esp.contagem["nf@luxor.com"] == [3, 3]
    # some do espelho sem sumir do Outlook (ex.: estado antigo) e um e-mail volta pra caixa com data antiga
    del esp.itens[ee.id_do_email("E0")]
    ol.receber(_item("VOLTOU", D(2026, 9, 1, 8, 0), D(2026, 9, 1, 8, 0)))
    agora[0] = D(2026, 10, 20, 10, 2)
    esp.volta(ol)
    assert esp.contagem["nf@luxor.com"] == [4, 4]
    assert ee.id_do_email("VOLTOU") in _na_entrada(esp) and ee.id_do_email("E0") in _na_entrada(esp)


def test_sem_data_do_servidor_conta_pela_data_de_criacao(tmp_path, monkeypatch):
    ol, esp, _ = _montar(tmp_path, monkeypatch)
    ol.receber(_item("SEMDATA", None, D(2026, 10, 20, 9, 0)))
    esp.volta(ol)
    assert esp.contagem["nf@luxor.com"] == [1, 1]


def test_item_que_nao_da_pra_ler_nao_rele_toda_volta(tmp_path, monkeypatch):
    ol, esp, agora = _montar(tmp_path, monkeypatch)
    ol.receber(_item("OK", D(2026, 10, 20, 9, 0), D(2026, 10, 20, 9, 0)))
    ruim = _item("RUIM", D(2026, 10, 20, 9, 5), D(2026, 10, 20, 9, 5))
    ruim.ReceivedTime = ruim.CreationTime = None   # o Outlook não dá data nenhuma: não entra no espelho
    ol.receber(ruim)
    esp.volta(ol)
    assert esp.contagem["nf@luxor.com"] == [2, 1] and esp.contagem_relida == {"nf@luxor.com": 2}
    chamadas = []
    original = esp._recebido
    esp._recebido = lambda *a: (chamadas.append(1), original(*a))
    agora[0] = D(2026, 10, 20, 10, 2)
    esp.volta(ol)
    assert len(chamadas) == 0   # mesmo total no Outlook: não relê a caixa inteira de novo
