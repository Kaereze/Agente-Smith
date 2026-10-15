"""TRUE também na planilha do hotel (15/10/2026): o que a Central (ou a lista do robô) já tem como enviado vira
TRUE na coluna Enviado da planilha do hotel — só nessa coluna e só nas linhas certas."""
import sincronizar as sz

CFG = {"colunas": {"enviado": "Enviado", "carimbo": "Carimbo de data/hora", "email_hospede": ["E-mail"]},
       "formato_data_planilha": "americano"}
CAB = ["Carimbo de data/hora", "E-mail", "Nome", "Enviado"]
ARQ = {"id": "PLANILHA", "name": "Nota Fiscal (Barra) (respostas)"}


class Http:
    def __init__(self):
        self.chamadas = []

    def values_batch_update(self, id, body=None):
        self.chamadas.append((id, body))


class Cliente:
    def __init__(self):
        self.http_client = Http()


def _plano(origem, central, lista=frozenset()):
    lidas = [(ARQ, "Respostas ao formulário 1", origem)]
    o, fontes = sz.juntar_planilhas(lidas, CFG)
    novas, _ = sz.mesclar(o, central, CFG, lista)
    return sz.linhas_para_marcar_no_hotel(lidas, fontes, novas, CFG)


def test_letra_coluna():
    assert [sz._letra_coluna(i) for i in (0, 3, 25, 26, 27)] == ["A", "D", "Z", "AA", "AB"]


def test_marca_so_o_que_a_central_ja_enviou_e_respeita_linha_vazia():
    origem = [CAB,
              ["10/1/2026 9:00:00", "a@x.com", "Ana", "TRUE"],     # linha 2: já TRUE no hotel
              [],                                                 # linha 3: vazia no meio
              ["10/2/2026 10:00:00", "b@x.com", "Bia", ""],       # linha 4: enviada (TRUE na Central)
              ["10/3/2026 11:00:00", "c@x.com", "Caio", ""]]      # linha 5: ainda pendente
    central = [CAB,
               ["10/1/2026 9:00:00", "a@x.com", "Ana", "TRUE"],
               ["10/2/2026 10:00:00", "b@x.com", "Bia", "TRUE"],
               ["10/3/2026 11:00:00", "c@x.com", "Caio", "FALSE"]]
    assert _plano(origem, central) == [(ARQ, "Respostas ao formulário 1", "D", [4])]


def test_lista_do_robo_tambem_conta_e_sem_coluna_nao_mexe():
    enviada = {("2026-10-02", "10:00:00", "b@x.com")}
    origem = [CAB, ["10/2/2026 10:00:00", "b@x.com", "Bia", ""]]
    assert _plano(origem, [], enviada) == [(ARQ, "Respostas ao formulário 1", "D", [2])]
    sem = [["Carimbo de data/hora", "E-mail"], ["10/2/2026 10:00:00", "b@x.com"]]
    plano = _plano(sem, [], enviada)
    assert plano == [(ARQ, "Respostas ao formulário 1", None, [2])]
    cliente = Cliente()
    assert sz.marcar_true_nos_arquivos(cliente, plano) == (0, [ARQ["name"]])   # não cria coluna na planilha de ninguém
    assert cliente.http_client.chamadas == []


def test_escreve_so_a_coluna_enviado():
    cliente = Cliente()
    assert sz.escrever_true_no_hotel(cliente, "PLANILHA", "Respostas ao formulário 1", "D", [4, 9]) == 2
    (pid, corpo), = cliente.http_client.chamadas
    assert pid == "PLANILHA" and corpo["valueInputOption"] == "USER_ENTERED"
    assert [d["range"] for d in corpo["data"]] == ["'Respostas ao formulário 1'!D4", "'Respostas ao formulário 1'!D9"]
    assert all(d["values"] == [["TRUE"]] for d in corpo["data"])
