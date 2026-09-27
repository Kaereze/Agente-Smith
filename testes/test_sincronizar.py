"""Cópia da planilha de cada hotel pra Planilha Central (src/sincronizar.py)."""
from sincronizar import hotel_da_planilha, mesclar

CAB = ["Carimbo de data/hora", "Endereço de e-mail", "Nome", "Enviado"]


def _origem(*linhas):
    return [CAB] + [list(l) for l in linhas]


def test_central_sem_hora_e_dois_pedidos_no_mesmo_dia_nao_duplica(cfg):
    """Caso real do Biton: a Central colada à mão perdeu a hora ('7/31/2025')."""
    origem = _origem(["31/07/2025 08:53:23", "mara@x.com", "Mara 1", "TRUE"],
                     ["31/07/2025 08:56:48", "mara@x.com", "Mara 2", ""],
                     ["02/08/2025 17:17:32", "lf@x.com", "LF", "FALSE"])
    central = [CAB, ["7/31/2025", "mara@x.com", "Mara 1", "TRUE"],
               ["7/31/2025", "mara@x.com", "Mara 2", "TRUE"],        # o robô já tinha marcado
               ["8/2/2025", "lf@x.com", "LF", "FALSE"]]
    novas, r = mesclar(origem, central, cfg)
    assert r["so_na_central"] == 0 and len(novas) == 4            # nada duplicado
    assert [l[3] for l in novas[1:]] == [True, True, False]       # TRUE da Central preservado
    assert novas[1][0] == "31/07/2025 08:53:23"                   # a hora volta (vem da planilha do hotel)
    assert r == {"linhas": 3, "true_origem": 1, "true_da_central": 1, "true_da_lista": 0, "pendentes": 1, "so_na_central": 0,
                 "ultimo_antigo": __import__("datetime").datetime(2025, 7, 31, 8, 53, 23)}   # TRUE do hotel = robô antigo


def test_ja_enviada_pelo_robo_nao_volta_a_ficar_pendente(cfg):
    origem = _origem(["9/16/2026 10:59:43", "weber@x.com", "Weber", ""])
    novas, r = mesclar(origem, [], cfg, chaves_ja_enviadas={("2026-09-16", "10:59:43", "weber@x.com")})
    assert novas[1][3] is True and r["true_da_lista"] == 1


def test_linha_que_so_existe_na_central_e_mantida(cfg):
    origem = _origem(["01/09/2026 10:00:00", "a@x.com", "A", ""])
    central = [CAB, ["01/09/2026 10:00:00", "a@x.com", "A", ""], ["05/09/2026 11:00:00", "colada@x.com", "Só aqui", "TRUE"]]
    novas, r = mesclar(origem, central, cfg)
    assert r["so_na_central"] == 1 and novas[-1][1] == "colada@x.com"


def test_mesmo_dia_mas_hora_diferente_nao_casa(cfg):
    origem = _origem(["01/09/2026 10:00:00", "a@x.com", "A", ""])
    central = [CAB, ["01/09/2026 15:30:00", "a@x.com", "Outro pedido", "TRUE"]]
    novas, r = mesclar(origem, central, cfg)
    assert novas[1][3] is False and r["so_na_central"] == 1        # não herda TRUE de outro pedido


def test_planilha_sem_coluna_enviado_ganha_a_coluna(cfg):
    novas, _ = mesclar([["Carimbo de data/hora", "Endereço de e-mail"], ["01/09/2026 10:00:00", "a@x.com"]], [], cfg)
    assert novas[0][-1] == "Enviado" and novas[1][-1] is False


def test_nome_da_planilha_vira_hotel_do_cadastro(cfg):
    cfg["apelidos_hoteis"] = {"Lg Inn": "L GINN", "Mine Hotel": "MINI HOTEL"}
    cfg["fontes_hoteis"] = {"planilha_para_hotel": {"Nota Fiscal (Navegantes) (respostas)": "NAVEGANTESBPS"}}
    cadastro = {"l ginn": "L GINN", "mini hotel": "MINI HOTEL", "lagoa": "LAGOA", "navegantes": "NAVEGANTES"}
    assert hotel_da_planilha("Nota Fiscal (Lg Inn) (respostas)", cfg, cadastro) == "L GINN"
    assert hotel_da_planilha("Solicitação Nota Fiscal (Mine Hotel) (respostas)", cfg, cadastro) == "MINI HOTEL"
    assert hotel_da_planilha("Nota Fiscal Lagoa (respostas)", cfg, cadastro) == "LAGOA"
    assert hotel_da_planilha("Nota Fiscal (Navegantes) (respostas)", cfg, cadastro) == "NAVEGANTESBPS"
    assert hotel_da_planilha("Solicitação Nota Fiscal (Navegantes) (respostas)", cfg, cadastro) == "NAVEGANTES"
    assert hotel_da_planilha("Formulário NF (TesteHotel) (respostas)", cfg, cadastro) is None


def test_hora_sem_zero_na_frente_casa(cfg):
    """Caso real do Royal: Central '05/08/2026 9:35:54' x planilha do hotel '05/08/2026 09:35:54'."""
    origem = _origem(["05/08/2026 09:35:54", "a@x.com", "A", ""])
    central = [CAB, ["05/08/2026 9:35:54", "a@x.com", "A", "TRUE"]]
    novas, r = mesclar(origem, central, cfg)
    assert r["so_na_central"] == 0 and novas[1][3] is True
