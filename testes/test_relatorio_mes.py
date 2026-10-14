"""Gerência v2 (14/10/2026): relatório do mês contra o mês anterior, nos mesmos dias."""
import datetime

import relatorio_semana as rs

D = datetime.date


def test_periodo_mes_corrente_compara_os_mesmos_dias():
    assert rs.periodo(D(2026, 10, 14), "mes", 0) == (D(2026, 10, 1), D(2026, 10, 31), D(2026, 9, 1), D(2026, 9, 14))


def test_periodo_mes_passado_inteiro_e_virada_de_ano():
    assert rs.periodo(D(2026, 10, 14), "mes", 1) == (D(2026, 9, 1), D(2026, 9, 30), D(2026, 8, 1), D(2026, 8, 30))
    assert rs.periodo(D(2026, 1, 10), "mes", 0)[2:] == (D(2025, 12, 1), D(2025, 12, 10))
    assert rs.periodo(D(2026, 3, 31), "mes", 0)[2:] == (D(2026, 2, 1), D(2026, 2, 28))   # fevereiro curto


def test_montar_mes_traz_hoteis_com_o_periodo_anterior():
    dados = {"Clara": [{"dia": D(2026, 10, 3), "hotel": "LUXOR", "recebidos": 10, "enviados": 8, "ligacoes": 1, "subst_canc": 2, "nfs": 7},
                       {"dia": D(2026, 9, 3), "hotel": "LUXOR", "recebidos": 4, "enviados": 4, "ligacoes": 0, "subst_canc": 0, "nfs": 3}]}
    r = rs.montar(dados, D(2026, 10, 14), 0, [], "mes")
    assert r["tipo"] == "mes" and r["total"]["nfs"] == 7 and r["total_anterior"]["nfs"] == 3
    h = r["hoteis_todos"][0]
    assert (h["recebidos"], h["recebidos_ant"], h["subst_canc"]) == (10, 4, 2)
    assert "mês anterior" in r["texto"]
