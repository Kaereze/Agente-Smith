"""Alarme de pedido parado (15/10/2026): pedido de formulário sem TRUE na Central há mais de 2 h vira aviso."""
import datetime

import saude

D = datetime.datetime


def _s(hotel, data, hora, enviado=False):
    return {"hotel": hotel, "data": data, "carimbo": f"{data[8:10]}/{data[5:7]}/{data[:4]} {hora}:00", "enviado": enviado}


def test_parado_ha_mais_de_2h_vira_aviso_agrupado_por_hotel():
    agora = D(2026, 10, 15, 14, 0)
    lista = [_s("RONDONÓPOLIS", "2026-10-15", "10:30"), _s("RONDONÓPOLIS", "2026-10-15", "11:10"),
             _s("LUXOR", "2026-10-14", "18:00"), _s("ONDINA", "2026-10-15", "13:20"),   # ONDINA: 40 min, ainda no prazo
             _s("BARRA", "2026-10-15", "09:00", enviado=True)]
    r = saude.pedidos_sem_envio(lista, agora)
    assert len(r) == 1 and r[0]["nivel"] == "erro"
    assert "3 pedido(s)" in r[0]["texto"] and "RONDONÓPOLIS (2)" in r[0]["texto"] and "LUXOR (1)" in r[0]["texto"]
    assert "ONDINA" not in r[0]["texto"] and "BARRA" not in r[0]["texto"]


def test_tudo_enviado_ou_fora_do_horario_nao_avisa():
    assert saude.pedidos_sem_envio([_s("BARRA", "2026-10-15", "09:00", enviado=True)], D(2026, 10, 15, 14, 0)) == []
    assert saude.pedidos_sem_envio([_s("BARRA", "2026-10-14", "09:00")], D(2026, 10, 15, 3, 0)) == []   # madrugada
