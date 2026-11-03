"""Chamada ao Google com limite de tempo (29/10/2026, João: a volta lenta tem que levar no máximo 30 s)."""
import pytest

import rede_util
import sheets


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def passar(self, s):
        self.t += s


def _passageiro(e):
    return "timed out" in str(e)


def test_orcamento_corta_a_espera_que_estouraria_o_limite():
    r, dormiu = Relogio(), []

    def func():
        r.passar(15)                              # cada tentativa leva o tempo limite todo
        raise TimeoutError("Read timed out")
    with pytest.raises(TimeoutError):
        rede_util.com_retry(func, _passageiro, tentativas=3, espera_inicial=2, orcamento=30, esperar=lambda s: (dormiu.append(s), r.passar(s)),
                            relogio=r)
    assert dormiu == [2] and r.t == 32                                                  # 15 + 2 de espera + 15 = 32 s: a 3ª tentativa nem começa


def test_sem_orcamento_continua_como_antes():
    r, dormiu = Relogio(), []
    chamadas = []

    def func():
        chamadas.append(1)
        if len(chamadas) < 3:
            raise TimeoutError("Read timed out")
        return "ok"
    assert rede_util.com_retry(func, _passageiro, tentativas=5, espera_inicial=10, esperar=dormiu.append, relogio=r) == "ok"
    assert dormiu == [10, 20]


def test_erro_que_nao_e_passageiro_sobe_na_hora_e_sucesso_nao_espera():
    def func():
        raise ValueError("aba não existe")
    with pytest.raises(ValueError):
        rede_util.com_retry(func, _passageiro, orcamento=30, esperar=lambda s: pytest.fail("não devia esperar"))
    assert rede_util.com_retry(lambda: 7, _passageiro, orcamento=30) == 7


def test_google_usa_15_s_por_tentativa_e_30_s_no_total():
    assert sheets.TIMEOUT_GOOGLE_SEGUNDOS == 15 and sheets.LIMITE_CHAMADA_GOOGLE_SEGUNDOS == 30
    # no pior caso: 15 s + 2 s de espera + 15 s = 32 s (antes: 5 tentativas de 30 s e esperas de 10/20/40/80 s = ~5 min)
    pior = 2 * sheets.TIMEOUT_GOOGLE_SEGUNDOS + 2
    assert pior <= 35
