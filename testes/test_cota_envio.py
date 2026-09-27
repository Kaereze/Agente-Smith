"""Cota de envio (src/cota_envio.py): conta os envios da última hora."""
import datetime

from cota_envio import calcular_cota

AGORA = datetime.datetime(2026, 9, 24, 17, 0)


def _ha(minutos, n=1):
    return (AGORA - datetime.timedelta(minutes=minutos), n)


def test_so_conta_a_ultima_hora():
    r = calcular_cota([_ha(5, 3), _ha(59), _ha(61, 10), _ha(300, 7)], 250, AGORA)
    assert r["usados_hora"] == 4 and r["sobra_hora"] == 246 and r["usados_24h"] == 21


def test_libera_quando_o_mais_antigo_da_janela_fizer_uma_hora():
    r = calcular_cota([_ha(5), _ha(40)], 250, AGORA)
    assert r["proxima_liberacao"] == "17:20"


def test_estourou_a_cota_sobra_zero():
    r = calcular_cota([_ha(10, 300)], 250, AGORA)
    assert r["sobra_hora"] == 0


def test_sem_envios():
    r = calcular_cota([], 250, AGORA)
    assert r["sobra_hora"] == 250 and r["proxima_liberacao"] == "" and len(r["por_hora"]) == 24
