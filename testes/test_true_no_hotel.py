"""TRUE também na planilha do hotel (15/10/2026): o que a Central (ou a lista do robô) já tem como enviado vira
TRUE na coluna Enviado da planilha do hotel — só nessa coluna e só nas linhas certas."""
import sincronizar as sz

CFG = {"colunas": {"enviado": "Enviado", "carimbo": "Carimbo de data/hora", "email_hospede": ["E-mail"]},
       "formato_data_planilha": "americano"}
CAB = ["Carimbo de data/hora", "E-mail", "Nome", "Enviado"]


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
    novas, _ = sz.mesclar(origem, central, CFG)
    assert sz.linhas_para_marcar_no_hotel(origem, novas, CFG) == ("D", [4])


def test_lista_do_robo_tambem_conta_e_sem_coluna_nao_mexe():
    origem = [CAB, ["10/2/2026 10:00:00", "b@x.com", "Bia", ""]]
    novas, _ = sz.mesclar(origem, [], CFG, {("2026-10-02", "10:00:00", "b@x.com")})
    assert sz.linhas_para_marcar_no_hotel(origem, novas, CFG) == ("D", [2])
    sem = [["Carimbo de data/hora", "E-mail"], ["10/2/2026 10:00:00", "b@x.com"]]
    novas, _ = sz.mesclar(sem, [], CFG, {("2026-10-02", "10:00:00", "b@x.com")})
    assert sz.linhas_para_marcar_no_hotel(sem, novas, CFG) == (None, [])


def test_escreve_so_a_coluna_enviado():
    chamadas = []

    class Http:
        def values_batch_update(self, id, body=None):
            chamadas.append((id, body))

    class Cliente:
        http_client = Http()

    assert sz.escrever_true_no_hotel(Cliente(), "PLANILHA", "Respostas ao formulário 1", "D", [4, 9]) == 2
    (pid, corpo), = chamadas
    assert pid == "PLANILHA" and corpo["valueInputOption"] == "USER_ENTERED"
    assert [d["range"] for d in corpo["data"]] == ["'Respostas ao formulário 1'!D4", "'Respostas ao formulário 1'!D9"]
    assert all(d["values"] == [["TRUE"]] for d in corpo["data"])
