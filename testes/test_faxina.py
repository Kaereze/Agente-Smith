import datetime

import pytest

import app_dados as d
import envio_nf
import faxina
from conftest import CENTRAL, ESTRELA

HOJE = datetime.date(2026, 10, 20)
VELHO = datetime.datetime(2026, 10, 1, 10, 0).astimezone()
NOVO = datetime.datetime(2026, 10, 19, 10, 0).astimezone()
CAR, EMAIL = "9/30/2026 10:00:00", "ana@x.com"


def ev(acao, valor="", quando=VELHO, carimbo=CAR, email=EMAIL, agente="Robô"):
    return d.evento(quando, agente, "PC", ESTRELA, carimbo, email, acao, valor)


def _linhas():
    return [d.CABECALHO_TRATAMENTO,
            ev(d.NF, "700"), ev(d.OBS, "NF 700 confirmada automaticamente: CPF do PDF confere (Ana Souza)"),
            ev(d.OBS, "E-mail com a NF 700 enviado para ana@x.com em 01/10/2026 09:00 [m-abc]"),
            ev(d.TRATATIVA, "E-mail ao hóspede em 2026-09-30 11:00: Dados [m-def]"),
            ev(d.DIVIDIDA, "nao"), ev(d.OBS, "Hóspede aceita nota única: “pode ser uma só” (e-mail)"),
            ev(d.ASSUMIR, agente="Clara"), ev(d.LIBERAR, agente="Clara"),
            ev(d.NF, "1", carimbo="1/5/2026 10:00:00", email="velho@x.com"),       # solicitação de janeiro
            ev(d.NF, "2", carimbo="1/6/2026 10:00:00", email="mexida@x.com"),
            ev(d.OBS, "anotação nova", quando=NOVO, carimbo="1/6/2026 10:00:00", email="mexida@x.com"),
            ev(d.NF, "701", quando=NOVO)]


def _datas():
    return {d.chave(ESTRELA, CAR, EMAIL): "2026-09-30", d.chave(ESTRELA, "1/5/2026 10:00:00", "velho@x.com"): "2026-01-05",
            d.chave(ESTRELA, "1/6/2026 10:00:00", "mexida@x.com"): "2026-01-06"}


def test_resumo_guarda_o_estado_e_tira_as_provas():
    linhas = _linhas()
    k, novas = faxina.compactar_tratamento(linhas, _datas(), HOJE)
    assert k == 11                                         # 10 linhas antigas; as 2 de ontem ficam como estão
    textos = [l[7] for l in novas]
    assert "NF 700 confirmada automaticamente: CPF do PDF confere (Ana Souza)" not in textos   # prova: sai
    assert any("[m-abc]" in t for t in textos) and any("[m-def]" in t for t in textos)         # marcas: ficam
    assert not any(l[6] in (d.ASSUMIR, d.LIBERAR) for l in novas)                               # já liberada
    assert not any("velho@x.com" == l[5] for l in novas)   # janeiro, sem novidade: sai inteira
    assert any("mexida@x.com" == l[5] for l in novas)      # janeiro, mas mexeram ontem: o resumo fica
    antes, depois = d.dobrar_eventos(linhas), d.dobrar_eventos([linhas[0]] + novas + linhas[k:])
    ch = d.chave(ESTRELA, CAR, EMAIL)
    assert depois[ch]["nfs"] == ["700", "701"] and depois[ch]["dividida"] is False
    assert faxina._impressao(antes[ch]) == faxina._impressao(depois[ch])
    k2, novas2 = faxina.compactar_tratamento([linhas[0]] + novas + linhas[k:], _datas(), HOJE)
    assert sorted(map(tuple, novas2)) == sorted(map(tuple, novas))   # rodar de novo não muda nada


def test_trava_nao_deixa_gravar_se_o_estado_mudaria(monkeypatch):
    monkeypatch.setattr(faxina, "resumo_da_solicitacao", lambda ls: [])   # resumo "quebrado": perde a NF
    with pytest.raises(RuntimeError, match="nada gravado"):
        faxina.compactar_tratamento(_linhas(), _datas(), HOJE)


def test_abas_curtas_perdem_so_o_comeco_velho():
    linhas = [["Quando"], ["2026-10-10T10:00:00"], ["2026-10-16T10:00:00"], ["2026-10-19T10:00:00"]]
    assert faxina.prefixo_velho(linhas, 3, HOJE) == 2
    assert faxina.prefixo_velho([["Quando"]], 3, HOJE) == 0


def test_rodar_na_planilha(cfg, planilha, tmp_path, monkeypatch):
    monkeypatch.setattr(faxina, "CAMINHO", tmp_path / "faxina.json")
    monkeypatch.setattr(faxina, "PASTA_ESTADO", tmp_path)
    hoje = datetime.date.today()
    velho = (datetime.datetime.now() - datetime.timedelta(days=10)).astimezone()
    sols = d.ler_solicitacoes(ESTRELA, "ESTRELA CENTRO", planilha.aba(ESTRELA), cfg)
    s = sols[0]
    planilha.criar_aba_log(CENTRAL, d.ABA_TRATAMENTO, d.CABECALHO_TRATAMENTO)
    planilha.anexar_linhas(CENTRAL, d.ABA_TRATAMENTO, [
        d.evento(velho, "Robô", "PC", s["aba"], s["carimbo"], s["email"], d.NF, "55"),
        d.evento(velho, "Robô", "PC", s["aba"], s["carimbo"], s["email"], d.OBS, "NF 55 confirmada automaticamente: CPF"),
        d.evento(velho, "Robô", "PC", s["aba"], s["carimbo"], s["email"], d.OBS, "NF 55 confirmada automaticamente: CNPJ")])
    planilha.criar_aba_log(CENTRAL, envio_nf.ABA_FILA, envio_nf.CAB_FILA)
    planilha.anexar_linhas(CENTRAL, envio_nf.ABA_FILA, [[velho.isoformat(), "ENV-1", "PEDIDO", "PC", "x", "{}"],
                                                        [velho.isoformat(), "ENV-1", "ENVIADO", "PC", "x", "{}"]])
    planilha.planilhas[CENTRAL]["Emails_PC-A"] = [["ID"]]
    planilha.planilhas[CENTRAL]["Correio_PC-A"] = [["ID"]]
    r = faxina.rodar(planilha, cfg, hoje=hoje)
    assert planilha.aba(d.ABA_TRATAMENTO) == [d.CABECALHO_TRATAMENTO,
                                              [velho.isoformat(timespec="seconds"), "Robô", "PC", s["aba"], s["carimbo"],
                                               s["email"], d.NF, "55"]]
    assert planilha.aba(envio_nf.ABA_FILA) == [envio_nf.CAB_FILA]
    assert "Emails_PC-A" not in planilha.planilhas[CENTRAL] and "Correio_PC-A" in planilha.planilhas[CENTRAL]
    assert set(r) >= {d.ABA_TRATAMENTO, envio_nf.ABA_FILA, "Emails_PC-A"}
    assert list(tmp_path.glob("backup_tratamento_*.json"))            # cópia de segurança antes
    assert faxina.rodar(planilha, cfg, hoje=hoje) is None              # 1x por dia
