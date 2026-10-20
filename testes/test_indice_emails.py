"""Índice local dos e-mails (usuário, 20/10/2026: pesquisa instantânea). Dados inventados."""
import datetime
import re

import indice_emails as ie

D = datetime.datetime
AGORA = D(2026, 10, 20, 15, 0)


def _linha(i, assunto="Nota fiscal", nome="Marina Exemplo Costa", de="marina.exemplo@gmail.com", texto="", quando=AGORA,
           pasta="entrada", caixa="nf@luxor.com"):
    return {"id": i, "entry": "E" + i, "pasta": pasta, "caixa": caixa, "hotel": "LUXOR", "de": de, "nome": nome,
            "para": caixa, "assunto": assunto, "quando": quando.isoformat(timespec="seconds"), "previa": texto[:50],
            "anexos": ["voucher.pdf"], "texto": texto}


def test_consulta_sem_acento_e_palavra_pela_metade():
    assert ie.consulta_fts("Marina Exem") == '"marina"* AND "exem"*'
    assert ie.consulta_fts('a"b') == '"a"* AND "b"*'   # aspas nunca quebram a consulta
    assert ie.consulta_fts("123.456.789-09") == '"123"* AND "456"* AND "789"* AND "09"*'


def test_grava_e_acha_na_hora(tmp_path):
    ind = ie.Indice(tmp_path / "i.sqlite")
    ind.gravar([_linha("a", texto="Preciso incluir UEM / Projeto Exemplo na nota", quando=AGORA - datetime.timedelta(days=3)),
                _linha("b", nome="José Conceição Teste", de="jose.teste@empresa.com", assunto="Reserva 999",
                       texto="Segue o CPF 529.982.247-25", quando=AGORA)])
    assert [r["id"] for r in ind.buscar("Exem")] == ["a"]                 # palavra pela metade, no nome
    assert [r["id"] for r in ind.buscar("conceicao")] == ["b"]            # sem acento acha com acento
    assert [r["id"] for r in ind.buscar("projeto exemplo")] == ["a"]      # frase no texto do hóspede
    assert [r["id"] for r in ind.buscar("529.982.247-25")] == ["b"]       # CPF com pontuação
    assert [r["id"] for r in ind.buscar("luxor")] == ["b", "a"]           # o mais novo primeiro
    assert ind.buscar("lu") == []                                         # menos de 3 letras: nada
    r = ind.buscar("empresa.com")[0]
    assert r["anexos"] == ["voucher.pdf"] and r["caixa"] == "nf@luxor.com" and "texto" not in r


def test_mesmo_email_atualiza_e_faxina_tira_os_de_mais_de_12_meses(tmp_path):
    ind = ie.Indice(tmp_path / "i.sqlite")
    ind.gravar([_linha("a", assunto="Nota fiscal antiga"), _linha("v", assunto="Muito velho", quando=AGORA - datetime.timedelta(days=400))])
    ind.gravar([_linha("a", assunto="Assunto trocado")])
    assert ind.total() == 2 and ind.buscar("antiga") == [] and [r["id"] for r in ind.buscar("trocado")] == ["a"]
    assert ind.faxina(AGORA) == 1 and ind.buscar("velho") == [] and ind.total() == 1


def test_abre_de_novo_com_o_que_ja_tinha(tmp_path):
    ie.Indice(tmp_path / "i.sqlite").gravar([_linha("a")])
    assert [r["id"] for r in ie.Indice(tmp_path / "i.sqlite").buscar("marina")] == ["a"]


# ---------- Montador com um Outlook de mentira ----------
class Itens(list):
    """Restrict como o Outlook: [Campo] >= 'dd/mm/aaaa hh:mm' (AND [Campo] <= '...')."""
    def Restrict(self, filtro):
        conds = re.findall(r"\[(\w+)\] (>=|<=) '(\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d)'", filtro)
        saida = list(self)
        for campo, op, dd, mm, aa, h, m in conds:
            lim = D(int(aa), int(mm), int(dd), int(h), int(m))
            saida = [i for i in saida if (getattr(i, campo) >= lim if op == ">=" else getattr(i, campo) <= lim + datetime.timedelta(seconds=59))]
        return Itens(saida)

    def Sort(self, _campo, desc):
        self.sort(key=lambda i: i.ReceivedTime, reverse=desc)


class Tabela:
    """Como a tabela do Outlook (GetTable): só as colunas pedidas, em lotes."""
    COL = {"EntryID": "EntryID", "Subject": "Subject", "SenderName": "SenderName", "To": "To",
           "SenderEmailAddress": "SenderEmailAddress", "ReceivedTime": "ReceivedTime", "SentOn": "SentOn"}

    def __init__(self, itens):
        self.itens, self.pos, self.cols = list(itens), 0, []
        self.Columns = type("C", (), {"RemoveAll": lambda s: self.cols.clear(), "Add": lambda s, c: self.cols.append(c)})()

    def Sort(self, _campo, desc):
        self.itens.sort(key=lambda i: i.ReceivedTime, reverse=desc)

    @property
    def EndOfTable(self):
        return self.pos >= len(self.itens)

    def _valor(self, item, col):
        if col in self.COL:
            return getattr(item, self.COL[col], "")
        if col.endswith("textdescription"):
            return item.Body[:255]
        if col.endswith("hasattachment"):
            return bool(item.Attachments)
        return ""   # PR_SENDER_SMTP_ADDRESS: POP3 não preenche

    def GetArray(self, n):
        lote = self.itens[self.pos:self.pos + n]
        self.pos += n
        return tuple(tuple(self._valor(i, c) for c in self.cols) for i in lote)


class Pasta:
    def __init__(self):
        self.Items = Itens()

    def GetTable(self, filtro):
        return Tabela(self.Items.Restrict(filtro))


class Item:
    Class = 43

    def __init__(self, eid, quando, assunto="Nota fiscal", corpo="Bom dia, preciso da nota"):
        self.EntryID, self.ReceivedTime, self.SentOn = eid, quando, quando
        self.LastModificationTime = quando
        self.Subject, self.Body = assunto, corpo
        self.SenderEmailAddress, self.SenderName = "marina.exemplo@gmail.com", "Marina Exemplo Costa"
        self.Recipients, self.Attachments, self.To = [], [], "Marina Exemplo Costa"

    @property
    def PropertyAccessor(self):
        raise RuntimeError("sem cabeçalhos")


class Outlook:
    def __init__(self, caixa="nf@luxor.com"):
        self.pastas = {6: Pasta(), 5: Pasta(), 3: Pasta()}
        self.GetItemFromID = lambda eid: next(i for p in self.pastas.values() for i in p.Items if i.EntryID == eid)
        loja = type("Loja", (), {"GetDefaultFolder": lambda s, n: self.pastas[n]})()
        self.Accounts = [type("Conta", (), {"SmtpAddress": caixa, "DeliveryStore": loja})(),
                         type("Conta", (), {"SmtpAddress": "pessoal@gmail.com", "DeliveryStore": loja})()]


class Cronometro:
    """Cada olhada no relógio = 0,05 s: um passo de 1 s lê uns 15-20 e-mails."""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.05
        return self.t


def _montar_tudo(mont, ol, caixas, limite=500):
    for n in range(limite):
        if mont.passo(ol, caixas) == ie.PAUSA_PRONTO:
            return n + 1
    raise AssertionError("não terminou")


def test_monta_do_mais_novo_pro_mais_velho_aos_poucos_e_so_12_meses(tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "LINHAS_POR_VEZ", 3)   # a tabela de verdade é grande: aqui, poucas linhas por vez
    ol, agora = Outlook(), [AGORA]
    for k in range(60):
        ol.pastas[6].Items.append(Item(f"E{k}", AGORA - datetime.timedelta(hours=k * 7), assunto=f"Pedido {k}"))
    ol.pastas[6].Items.append(Item("VELHO", AGORA - datetime.timedelta(days=500), assunto="Pedido velho"))
    ol.pastas[5].Items.append(Item("S1", AGORA - datetime.timedelta(days=1), assunto="RE: Pedido 3"))
    ind = ie.Indice(tmp_path / "i.sqlite")
    mont = ie.Montador(ind, relogio=lambda: agora[0], cronometro=Cronometro())
    caixas = {"nf@luxor.com": "LUXOR"}
    assert mont.passo(ol, caixas) == ie.PAUSA_MONTANDO and 0 < ind.total() < 61   # 1º passo: só uma parte
    ids = {r["id"] for r in ind.buscar("pedido", limite=200)}
    assert ie.ee.id_do_email("E0") in ids and ie.ee.id_do_email("E59") not in ids   # os mais novos primeiro
    passos = _montar_tudo(mont, ol, caixas)
    assert passos >= 1 and mont.pronto
    assert ind.total() == 61   # 60 da entrada + 1 enviado; o de 500 dias e a caixa pessoal ficam de fora
    assert ind.buscar("velho") == [] and {r["pasta"] for r in ind.buscar("pedido 3")} == {"entrada", "enviado"}


def test_email_novo_entra_e_o_que_saiu_da_pasta_sai(tmp_path):
    ol, agora = Outlook(), [AGORA]
    ol.pastas[6].Items.extend([Item("A", AGORA - datetime.timedelta(hours=2), assunto="Primeiro pedido"),
                               Item("B", AGORA - datetime.timedelta(hours=1), assunto="Segundo pedido")])
    ind = ie.Indice(tmp_path / "i.sqlite")
    crono = Cronometro()
    mont = ie.Montador(ind, relogio=lambda: agora[0], cronometro=crono)
    caixas = {"nf@luxor.com": "LUXOR"}
    _montar_tudo(mont, ol, caixas)
    # chega um e-mail novo e o B vai pra Itens Excluídos (no Outlook ganha outro EntryID)
    agora[0] = AGORA + datetime.timedelta(minutes=5)
    novo = Item("C", AGORA + datetime.timedelta(minutes=4), assunto="Terceiro pedido")
    ol.pastas[6].Items.append(novo)
    b = next(i for i in ol.pastas[6].Items if i.EntryID == "B")
    ol.pastas[6].Items.remove(b)
    ol.pastas[3].Items.append(Item("B2", b.ReceivedTime, assunto="Segundo pedido"))
    ol.pastas[3].Items[-1].LastModificationTime = agora[0]
    crono.t += ie.CONFERIR_SAIDOS_SEGUNDOS
    mont.passo(ol, caixas)
    assert [r["id"] for r in ind.buscar("terceiro")] == [ie.ee.id_do_email("C")]
    assert [r["pasta"] for r in ind.buscar("segundo")] == ["excluido"]   # só a cópia na lixeira, não a da entrada


def test_rede_buscar_responde_pelo_indice(tmp_path, monkeypatch):
    import app_servidor
    ind = ie.Indice(tmp_path / "i.sqlite")
    ind.gravar([_linha("a")])
    falso = type("Estado", (), {"indice": ind, "montador": type("M", (), {"pronto": False})()})()
    monkeypatch.setattr(app_servidor.socket, "gethostname", lambda: "PC-A")
    r = app_servidor.Estado.rede_buscar(falso, {"q": "marina"})
    assert r["fonte"] == "indice" and r["completo"] is False and r["resultados"][0]["pc"] == "PC-A"


def test_texto_inteiro_e_anexos_entram_na_segunda_etapa(tmp_path):
    ol, agora = Outlook(), [AGORA]
    longo = Item("L", AGORA - datetime.timedelta(hours=1), corpo="Bom dia. " + "x " * 200 + "Meu CPF é 529.982.247-25")
    com_anexo = Item("A", AGORA - datetime.timedelta(hours=2), corpo="Segue o voucher")
    com_anexo.Attachments = [type("Anexo", (), {"FileName": "voucher-reserva-777.pdf"})()]
    ol.pastas[6].Items.extend([longo, com_anexo])
    ind = ie.Indice(tmp_path / "i.sqlite")
    mont = ie.Montador(ind, relogio=lambda: agora[0], cronometro=Cronometro())
    caixas = {"nf@luxor.com": "LUXOR"}
    mont._montar("nf@luxor.com", "entrada", ol.pastas[6], "LUXOR", AGORA, float("inf"))   # só a etapa rápida
    assert ind.total() == 2 and ind.buscar("529.982.247-25") == [] and ind.buscar("voucher-reserva-777") == []
    assert len(ind.a_completar(10)) == 2   # texto cortado em 255 e anexo sem nome
    _montar_tudo(mont, ol, caixas)
    assert [r["id"] for r in ind.buscar("529.982.247-25")] == [ie.ee.id_do_email("L")]
    achado = ind.buscar("voucher reserva 777")
    assert [r["id"] for r in achado] == [ie.ee.id_do_email("A")] and achado[0]["anexos"] == ["voucher-reserva-777.pdf"]
    assert ind.a_completar(10) == []
