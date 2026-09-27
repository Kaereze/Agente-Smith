"""Convivência com o robô antigo (src/robo_antigo.py)."""
import datetime

import robo_antigo as ra
from modelos import Hotel, Solicitacao

H = Hotel(aba="x", nome="BAHIA", operador="nf@bahia", planilha_id="p")
AGORA = datetime.datetime(2026, 9, 27, 12, 0, 0)


def _s(carimbo, email="ze@x.com", hotel=H):
    return Solicitacao(hotel=hotel, linha=2, carimbo=carimbo, email_hospede=email, nome_titulo="Zé",
                       campos=[], formato_data="brasileiro")


def test_le_o_horario_do_email_antigo():
    corpo = "Enviado em: Fri Sep 25 2026 22:58:03 GMT-0300 (Brasilia Standard Time)"
    assert ra.momento_do_email_antigo(corpo) == datetime.datetime(2026, 9, 25, 22, 58, 3)


def test_diaria_e_consumo_do_mesmo_hospede_sao_pedidos_diferentes():
    """Mesmo hóspede, mesmos dados, 2 formulários (diária e consumo): só o que o antigo mandou sai da fila."""
    diaria, consumo = _s("25/09/2026 22:58:03"), _s("25/09/2026 23:04:41")
    enviados = {ra.chave("ZE@x.com", datetime.datetime(2026, 9, 25, 22, 58, 3)): "25/09 22:59"}
    ja = ra.ja_mandadas_pelo_antigo([diaria, consumo], enviados)
    assert [s for s, _ in ja] == [diaria]


def test_hotel_com_robo_antigo_ativo_espera_a_vez_dele():
    outro = Hotel(aba="y", nome="LUXOR", operador="nf@luxor", planilha_id="p")
    recente, antiga, sem_antigo = _s("27/09/2026 11:30:00"), _s("27/09/2026 09:00:00"), _s("27/09/2026 11:30:00", hotel=outro)
    liberadas, aguardando = ra.separar([recente, antiga, sem_antigo], {"BAHIA"}, AGORA, 75)
    assert aguardando == [recente] and liberadas == [antiga, sem_antigo]


def test_atividade_do_antigo_expira(tmp_path):
    arq = tmp_path / "robo_antigo.json"
    ra.registrar_atividade(arq, {"BAHIA": datetime.datetime(2026, 9, 26, 10, 0), "BITON": datetime.datetime(2026, 9, 20, 10, 0),
                                 "LUXOR": None})
    assert ra.hoteis_ativos(arq, AGORA, dias=3) == {"BAHIA"}
