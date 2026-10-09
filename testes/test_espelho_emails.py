import datetime

import espelho_emails as ee

D = datetime.datetime


def test_corta_o_historico_colado_embaixo():
    texto = "Boa tarde,\nPreciso da nota no CNPJ 12.345.678/0001-90.\nObrigada\n\nDe: notafiscal@hotel.com\nEnviada em: ..."
    assert ee.sem_historico(texto) == "Boa tarde,\nPreciso da nota no CNPJ 12.345.678/0001-90.\nObrigada"
    assert ee.sem_historico("Oi\n\nEm seg., 5 de out. de 2026 às 10:00, Hotel <a@b> escreveu:\n> antigo") == "Oi"
    assert ee.sem_historico("só o texto") == "só o texto"
    gmail = "Boa tarde! O valor real pago.\n\nEm qui., 8 de out. de 2026 às 16:30, <nf@hotel.com.br>\nescreveu:\n> Prezada"
    assert ee.sem_historico(gmail) == "Boa tarde! O valor real pago."   # o Gmail quebra a linha antes do "escreveu:"


def test_automaticos_e_listas_ficam_de_fora():
    assert ee.e_automatico("no-reply@booking.com") and ee.e_automatico("naoresponda@banco.com.br")
    assert ee.e_automatico("reservas@decolar.com") and ee.e_automatico("x@empresa.com", "List-Unsubscribe: <mailto:..>")
    assert ee.e_automatico("sem-arroba")
    assert not ee.e_automatico("maria.souza@gmail.com") and not ee.e_automatico("financeiro@empresa.com.br")


def test_respondido_some_e_enviado_fica_so_24h():
    itens = {"a": {"pasta": "entrada", "de": "ana@x.com", "quando": "2026-10-06T10:00:00"},
             "b": {"pasta": "entrada", "de": "bia@x.com", "quando": "2026-10-06T10:00:00"},
             "c": {"pasta": "entrada", "de": "caio@x.com", "quando": ""},
             "velho": {"pasta": "entrada", "de": "duda@x.com", "quando": "2026-09-20T10:00:00"},
             "env_hoje": {"pasta": "enviado", "de": "nf@h.com", "quando": "2026-10-06T08:00:00"},
             "env_ontem": {"pasta": "enviado", "de": "nf@h.com", "quando": "2026-10-05T08:00:00"}}
    enviados = {"ana@x.com": D(2026, 10, 6, 11, 0), "bia@x.com": D(2026, 10, 6, 9, 0)}
    # ana respondida depois do e-mail (some); bia respondida ANTES (segue); sem data e +14 dias saem
    assert sorted(ee.resolver(itens, enviados, D(2026, 10, 6, 12, 0))) == ["b", "env_hoje"]


def test_aba_ida_e_volta():
    itens = {"x1": {"id": "x1", "pasta": "entrada", "caixa": "nf@hotel.com", "hotel": "LUXOR", "de": "ana@x.com",
                    "nome": "Ana", "assunto": "Nota", "quando": "2026-10-06T10:00:00", "anexos": ["a.pdf", "b.pdf"],
                    "texto": "Oi,   preciso\n\nda nota", "classes": ["pedido_nf"]}}
    linhas = ee.linhas_da_aba(itens, {"ana@x.com": D(2026, 10, 5, 9)}, "PC-A", D(2026, 10, 6, 12, 0), versao="v1")
    assert linhas[0] == ee.CABECALHO
    e, r = ee.ler_aba(linhas)
    assert (e["id"], e["hotel"], e["anexos"], e["pc"], e["previa"]) == ("x1", "LUXOR", ["a.pdf", "b.pdf"], "PC-A",
                                                                         "Oi, preciso da nota")
    assert e["classes"] == ["pedido_nf"] and e["versao_texto"] == "v1" and "texto" not in e
    assert (r["pasta"], r["de"], r["quando"]) == ("resposta", "ana@x.com", "2026-10-05T09:00:00")
    textos = ee.ler_textos(ee.linhas_textos({"x1": {**itens["x1"], "citado": "De: antigo"}}))
    assert textos == {"x1": ("Oi,   preciso\n\nda nota", "De: antigo")}


def test_classificacao_por_regras():
    assert ee.classificar("NF errada", "O valor está errado, precisa cancelar") [0] == "corrigir"
    assert "complementar" in ee.classificar("RE: NF", "Ficou faltando a nf da outra diária.")
    assert "cobranca" in ee.classificar("Nota", "Ainda não recebi a nota fiscal")
    assert ee.classificar("Dados", "Segue CNPJ 12.345.678/0001-90 para emissão da nota fiscal") == ["dados_tomador", "pedido_nf"]
    assert ee.classificar("Oi", "Obrigada pela estadia!") == []


def test_eventos_lido_nao_lido_excluir():
    linhas = [ee.CAB_EVENTOS, ["2026-10-08T10:00:00", "a", "LIDO", "Clara", "PC1"],
              ["2026-10-08T10:05:00", "b", "LIDO", "João", "PC2"], ["2026-10-08T10:06:00", "b", "NAO_LIDO", "João", "PC2"],
              ["2026-10-08T10:07:00", "c", "EXCLUIR", "Bernardo", "PC3"], ["2026-10-08T10:08:00", "d", "ASSUMIR", "X", "P"]]
    ev = ee.dobrar_eventos(linhas)
    assert ev["a"]["lido"] and ev["a"]["lido_por"] == "Clara" and ev["a"]["lido_em"] == "2026-10-08T10:00:00"
    assert not ev["b"]["lido"] and ev["c"]["excluido"] and ev["c"]["excluido_por"] == "Bernardo"
    assert "d" not in ev   # "Assumir" saiu (pedido do usuário)


def test_voucher_com_dois_quartos_e_nota_dividida():
    from controle_nf import quartos_da_reserva
    recibo = ("Recibo\nN° do itinerário da Hoteis.com: 72077571275512\n2 quartos para 3 diárias\nQuarto duplo econômico\n"
              "Reserva feita para: Lorena Perego Mendonça\nQuarto duplo econômico\nReserva feita para: José Eduardo Canteli\n"
              "Preço do quarto 1\nPreço do quarto 2\nTotal R$ 1.218,75")
    assert quartos_da_reserva(recibo) == (2, ["Lorena Perego Mendonça", "José Eduardo Canteli"])
    voucher = "Detalhes do quarto\nQuarto duplo\nReservado para\nMaria Silva, 2 adultos\nPreço do quarto 1\nTotal"
    assert quartos_da_reserva(voucher) == (1, ["Maria Silva"])
    assert quartos_da_reserva("Boa tarde, segue o comprovante de pagamento.") == (0, [])


def test_quartos_vao_e_voltam_pela_aba():
    p = {"x": {"id": "x", "pasta": "entrada", "caixa": "nf@h.com", "hotel": "BOA VIAGEM", "de": "a@b.com", "nome": "A",
               "assunto": "NF", "quando": "2026-10-06T18:14:32", "anexos": ["voucher.pdf"], "texto": "oi",
               "quartos": [2, ["Lorena Perego Mendonça", "José Eduardo Canteli"]]},
         "y": {"id": "y", "pasta": "entrada", "caixa": "nf@h.com", "hotel": "BOA VIAGEM", "de": "c@d.com", "nome": "C",
               "assunto": "Oi", "quando": "2026-10-06T10:00:00", "anexos": [], "texto": "oi"}}
    lidos = {e["id"]: e for e in ee.ler_aba(ee.linhas_da_aba(p, {}, "PC-A", D(2026, 10, 7)))}
    assert lidos["x"]["quartos"] == 2 and lidos["x"]["hospedes_quartos"] == ["Lorena Perego Mendonça", "José Eduardo Canteli"]
    assert lidos["y"]["quartos"] == 0 and lidos["y"]["hospedes_quartos"] == []


def test_hospede_dizendo_que_falta_nota():
    from controle_nf import reclama_falta_nota
    assert reclama_falta_nota("Bom dia,\nFicou faltando a nf referente a esse outro pagamento.") == \
        "Ficou faltando a nf referente a esse outro pagamento."
    assert reclama_falta_nota("Referente ao dia 29/09 e 30/09, ele ficou mais duas diárias além da que foi enviada.")
    assert reclama_falta_nota("A outra diária no hotel.")
    assert reclama_falta_nota("Boa tarde, recebi a nota, obrigada!") == ""
    assert reclama_falta_nota("Segue o comprovante de pagamento.") == ""


def test_resposta_do_hospede_nao_e_o_email_do_robo():
    from controle_nf import e_email_do_robo
    cod = "NF-CBC1B39537"
    assert e_email_do_robo("[1/1 ✅] Solicitação NF - JANGADEIRO - GERALDO", "...\nCódigo de envio: NF-CBC1B39537", cod)
    assert not e_email_do_robo("[1/1 ✅] RE: NF 196 - GERALDO", "Ficou faltando\n____\nDe: nf\nCódigo de envio: NF-CBC1B39537", cod)
    assert not e_email_do_robo("NF 196 - GERALDO", "Prezado\nDe: notafiscal\nCódigo de envio: NF-CBC1B39537", cod)


# ---------- volta completa com um Outlook falso ----------
class Lista(list):
    def Restrict(self, _filtro):
        return Lista(self)

    @property
    def Count(self):
        return len(self)


class Pasta:
    def __init__(self, eid):
        self.EntryID, self.Items = eid, Lista()


class Item:
    Class = 43

    def __init__(self, eid, de, assunto, corpo, quando, para=(), pasta=None, nome=""):
        self.EntryID, self.SenderEmailAddress, self.SenderName = eid, de, nome
        self.Subject, self.Body, self.ReceivedTime = assunto, corpo, quando
        self.SentOn = quando
        self.Recipients = [type("R", (), {"Address": p})() for p in para]
        self.Attachments = Lista()
        self.Parent = pasta

    @property
    def PropertyAccessor(self):
        raise RuntimeError("sem cabeçalhos")


class OutlookFalso:
    def __init__(self, caixa):
        self.entrada, self.enviados = Pasta("INBOX"), Pasta("SENT")
        self.lixo = Pasta("LIXO")
        pastas = {6: self.entrada, 5: self.enviados}
        loja = type("Loja", (), {"GetDefaultFolder": lambda s, n: pastas[n]})()
        self.Accounts = [type("Conta", (), {"SmtpAddress": caixa, "DeliveryStore": loja})()]

    def receber(self, item):
        item.Parent = self.entrada
        self.entrada.Items.append(item)

    def enviar(self, item):
        item.Parent = self.enviados
        self.enviados.Items.append(item)

    def excluir(self, item):
        self.entrada.Items.remove(item)
        item.Parent = self.lixo

    def GetItemFromID(self, eid):
        for p in (self.entrada, self.enviados):
            for i in p.Items:
                if i.EntryID == eid:
                    return i
        raise RuntimeError("não existe")


class Central:
    def __init__(self):
        self.abas = {"Cadastro_Hoteis": [["Hotel", "E-mail"], ["LUXOR", "nf@luxor.com"]]}
        self.leituras = 0

    def ler_abas(self, _pid, nomes):
        self.leituras += 1
        return {n: self.abas.get(n, []) for n in nomes}, {}

    def substituir_aba(self, _pid, aba, linhas):
        self.abas[aba] = [list(l) for l in linhas]


def test_volta_espelha_entrada_e_enviados_e_some_o_resolvido(tmp_path, monkeypatch):
    monkeypatch.setattr(ee, "CAMINHO_ESTADO", tmp_path / "espelho.json")
    monkeypatch.setattr(ee.socket, "gethostname", lambda: "PC-A")
    agora = [D(2026, 10, 8, 9, 0)]
    cfg = {"planilha_central_id": "C", "aba_cadastro_hoteis": "Cadastro_Hoteis", "conta_remetente": "robo@rede.com"}
    central, ol = Central(), OutlookFalso("nf@luxor.com")
    ana = Item("E1", "ana@gmail.com", "Nota fiscal", "Preciso da nota fiscal\n\nDe: antigo\nxx", D(2026, 10, 8, 8, 0), nome="Ana")
    bia = Item("E2", "bia@gmail.com", "Dúvida", "Oi, tudo bem?", D(2026, 10, 8, 8, 30))
    robo = Item("E3", "nf@luxor.com", "Solicitação NF - LUXOR", "lista\nCódigo de envio: NF-ABC", D(2026, 10, 8, 7, 0))
    booking = Item("E4", "noreply@booking.com", "Reserva", "nova reserva", D(2026, 10, 8, 7, 30))
    for i in (ana, bia, robo, booking):
        ol.receber(i)
    esp = ee.Espelho(central, cfg, relogio=lambda: agora[0])
    esp.volta(ol)
    resumo = ee.ler_aba(central.abas["Correio_PC-A"])
    assert sorted(e["de"] for e in resumo if e["pasta"] == "entrada") == ["ana@gmail.com", "bia@gmail.com"]
    textos = ee.ler_textos(central.abas["CorreioTexto_PC-A"])
    assert textos[ee.id_do_email("E1")] == ("Preciso da nota fiscal", "De: antigo\nxx")
    assert "pedido_nf" in next(e for e in resumo if e["de"] == "ana@gmail.com")["classes"]

    # 10:00 — respondeu a Ana pelo Outlook e excluiu a Bia: os dois somem; a resposta aparece em Enviados
    agora[0] = D(2026, 10, 8, 10, 0)
    ol.enviar(Item("S1", "nf@luxor.com", "RE: Nota fiscal", "Segue a NF", D(2026, 10, 8, 9, 50), para=["ana@gmail.com"]))
    ol.excluir(bia)
    esp.volta(ol)
    resumo = ee.ler_aba(central.abas["Correio_PC-A"])
    assert [e["pasta"] for e in resumo] == ["enviado", "resposta"]
    assert resumo[0]["para"] == "ana@gmail.com" and resumo[1]["de"] == "ana@gmail.com"
    assert ee.ler_textos(central.abas["CorreioTexto_PC-A"]).keys() == {ee.id_do_email("S1")}
    assert central.leituras == 1   # o cadastro é lido 1 vez e guardado (cota)

    # dia seguinte, 11:00 — o enviado passou de 24 h: some também; o espelho fica vazio, nada acumula
    agora[0] = D(2026, 10, 9, 11, 0)
    esp.volta(ol)
    assert [e["pasta"] for e in ee.ler_aba(central.abas["Correio_PC-A"])] == ["resposta"]


def test_espelho_nao_regrava_a_aba_se_nada_mudou(tmp_path, monkeypatch):
    monkeypatch.setattr(ee, "CAMINHO_ESTADO", tmp_path / "espelho.json")
    cfg = {"planilha_central_id": "C", "aba_cadastro_hoteis": "Cadastro_Hoteis"}
    central, ol = Central(), OutlookFalso("nf@luxor.com")
    ol.receber(Item("E1", "ana@gmail.com", "Nota", "Oi", D(2026, 10, 8, 8, 0)))
    gravacoes = []
    original = central.substituir_aba
    central.substituir_aba = lambda *a: (gravacoes.append(a[1]), original(*a))
    agora = [D(2026, 10, 8, 9, 0)]
    esp = ee.Espelho(central, cfg, relogio=lambda: agora[0])
    esp.volta(ol)
    agora[0] = D(2026, 10, 8, 9, 2)
    esp.volta(ol)
    assert len(gravacoes) == 2   # resumo + textos na 1ª volta; na 2ª, nada mudou: zero escritas


def test_nf_no_dropbox_vira_etiqueta_no_email_do_hospede(tmp_path, monkeypatch):
    import envio_nf
    from controle_nf import CATEGORIA_NF_EMITIDA
    monkeypatch.setattr(ee, "CAMINHO_ESTADO", tmp_path / "espelho.json")
    cfg = {"planilha_central_id": "C", "aba_cadastro_hoteis": "Cadastro_Hoteis"}
    central, ol = Central(), OutlookFalso("nf@luxor.com")
    ana = Item("E1", "ana@gmail.com", "Nota fiscal", "Reserva 62222", D(2026, 10, 8, 8, 0), nome="Ana")
    ana.Categories, salvos = "Nota dividida", []
    ana.Save = lambda: salvos.append(1)
    ol.receber(ana)
    ol.receber(Item("E2", "bia@gmail.com", "Dúvida", "Oi", D(2026, 10, 8, 8, 30)))
    monkeypatch.setattr(envio_nf, "listar_notas_dropbox", lambda cfg, forcar=False: [])
    monkeypatch.setattr(envio_nf, "notas_do_email", lambda e, cfg: [{"nf": "590"}] if e["de"] == "ana@gmail.com" else [])
    esp = ee.Espelho(central, cfg, relogio=lambda: D(2026, 10, 8, 9, 0))
    esp.volta(ol)
    assert ana.Categories == f"Nota dividida, {CATEGORIA_NF_EMITIDA}" and len(salvos) == 1   # a etiqueta que já tinha fica
    esp.volta(ol)
    assert len(salvos) == 1   # não marca de novo
