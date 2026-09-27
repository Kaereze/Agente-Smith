"""Conferência da cópia (src/conferir_copia.py): a Central está igual à planilha do hotel?"""
from conferir_copia import NOVIDADE, OK, PROBLEMA, classificar, comparar

CAB = ["Carimbo de data/hora", "Endereço de e-mail", "Nome do Hóspede", "CPF"]
CAB_C = CAB + ["Enviado"]


def test_tudo_igual(cfg):
    origem = [CAB, ["01/09/2026 10:00:00", "a@x.com", "Ana", "123"]]
    central = [CAB_C, ["01/09/2026 10:00:00", "a@x.com", "Ana", "123", "TRUE"]]
    r = comparar(origem, central, cfg)
    assert classificar(r, False)[0] == OK and r["linhas_origem"] == 1


def test_solicitacao_que_nao_chegou_na_central(cfg):
    origem = [CAB, ["01/09/2026 10:00:00", "a@x.com", "Ana", "1"], ["02/09/2026 11:00:00", "b@x.com", "Bia", "2"]]
    central = [CAB_C, ["01/09/2026 10:00:00", "a@x.com", "Ana", "1", "FALSE"]]
    r = comparar(origem, central, cfg)
    assert len(r["faltando"]) == 1 and "Bia" in r["faltando"][0]
    assert classificar(r, False)[0] == PROBLEMA            # a planilha não mudou: devia estar lá
    assert classificar(r, True)[0] == NOVIDADE             # chegou depois da última cópia


def test_dado_diferente_e_coluna_faltando(cfg):
    origem = [CAB + ["Telefone"], ["01/09/2026 10:00:00", "a@x.com", "Ana", "123", "999"]]
    central = [CAB_C, ["01/09/2026 10:00:00", "a@x.com", "Ana", "124", "FALSE"]]
    r = comparar(origem, central, cfg)
    assert r["colunas_faltando"] == ["Telefone"] and "CPF" in r["diferencas"][0]
    assert classificar(r, False)[0] == PROBLEMA


def test_true_do_hotel_que_ficou_pendente_na_central(cfg):
    """Isso faria o robô reenviar — tem que acusar."""
    origem = [CAB_C, ["01/09/2026 10:00:00", "a@x.com", "Ana", "1", "TRUE"]]
    central = [CAB_C, ["01/09/2026 10:00:00", "a@x.com", "Ana", "1", "FALSE"]]
    r = comparar(origem, central, cfg)
    assert len(r["true_sumiu"]) == 1 and classificar(r, False)[0] == PROBLEMA


def test_hora_sem_zero_e_linha_antiga_so_na_central(cfg):
    origem = [CAB, ["05/08/2026 09:35:54", "a@x.com", "Ana", "1"]]
    central = [CAB_C, ["05/08/2026 9:35:54", "a@x.com", "Ana", "1", "TRUE"],
               ["01/01/2026 08:00:00", "velho@x.com", "Antigo", "9", "TRUE"]]
    r = comparar(origem, central, cfg)
    assert r["faltando"] == [] and r["so_central"] == 1
    assert classificar(r, False)[0] == OK


def test_so_e_novidade_se_chegou_depois_da_ultima_copia():
    import datetime
    from conferir_copia import _todas_depois
    copia = datetime.datetime(2026, 9, 26, 9, 0, 0)
    assert _todas_depois([("2026-09-26", "09:10:00", "a@x.com")], copia)            # chegou depois: normal
    assert not _todas_depois([("2026-09-25", "12:00:00", "a@x.com")], copia)        # antiga: devia estar lá
    assert not _todas_depois([("2026-09-26", "09:10:00", "a@x.com")], None)


def test_aba_igual_nao_e_regravada():
    """A cópia lê tudo a cada 30 min, mas só regrava a aba quando algo mudou."""
    from sincronizar import _como_texto
    novas = [["Carimbo", "Enviado"], ["01/09/2026 10:00:00", True, ""]]
    da_planilha = [["Carimbo", "Enviado"], ["01/09/2026 10:00:00", "TRUE"]]
    assert _como_texto(novas) == _como_texto(da_planilha)
    assert _como_texto(novas) != _como_texto([["Carimbo", "Enviado"], ["01/09/2026 10:00:00", "FALSE"]])
