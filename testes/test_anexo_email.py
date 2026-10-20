"""Ver o anexo do hóspede no Painel (14/10/2026): o PC dono lê o anexo do Outlook, só das caixas dos hotéis."""
import base64

import pytest

import busca_outlook as bo


class Anexo:
    def __init__(self, nome, dados):
        self.FileName, self.Size, self._d = nome, len(dados), dados

    def SaveAsFile(self, caminho):
        open(caminho, "wb").write(self._d)


class Lista:
    def __init__(self, itens):
        self._i = itens
        self.Count = len(itens)

    def Item(self, k):
        return self._i[k - 1]


class Pasta:
    def __init__(self, eid):
        self.EntryID = eid
        self.Store = type("S", (), {"StoreID": "LOJA1"})()


class Loja:
    StoreID = "LOJA1"

    def GetDefaultFolder(self, n):
        return Pasta("ENTRADA" if n == 6 else f"P{n}")


class Conta:
    def __init__(self, smtp):
        self.SmtpAddress, self.DeliveryStore = smtp, Loja()


class Item:
    def __init__(self, anexos):
        self.Parent, self.Attachments = Pasta("ENTRADA"), Lista(anexos)


class Ns:
    def __init__(self, smtp, item):
        self.Accounts, self._item = [Conta(smtp)], item

    def GetItemFromID(self, entry):
        return self._item


def test_le_o_anexo_da_caixa_do_hotel_e_nao_deixa_arquivo():
    ns = Ns("nf@hotel.com", Item([Anexo("foto.jpg", b"\xff\xd8abc"), Anexo("voucher.pdf", b"%PDF-1")]))
    r = bo.ler_anexo(ns, "E1", {"nf@hotel.com": "HOTEL"}, "voucher.pdf")
    assert r["tipo"] == "application/pdf" and base64.b64decode(r["b64"]) == b"%PDF-1" and r["tamanho"] == 6


def test_caixa_pessoal_nao_sai_e_anexo_inexistente_avisa():
    ns = Ns("joao@pessoal.com", Item([Anexo("foto.jpg", b"x")]))
    with pytest.raises(PermissionError):
        bo.ler_anexo(ns, "E1", {"nf@hotel.com": "HOTEL"}, "foto.jpg")
    ns = Ns("nf@hotel.com", Item([Anexo("foto.jpg", b"x")]))
    with pytest.raises(KeyError):
        bo.ler_anexo(ns, "E1", {"nf@hotel.com": "HOTEL"}, "outro.png")
