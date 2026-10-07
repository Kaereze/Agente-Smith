import sincronizar as s


def test_so_le_hotel_com_versao_nova_ou_sem_versao():
    por_hotel = {"LUXOR": [{"id": "a", "version": "10"}], "BAHIA": [{"id": "b", "version": "7"}],
                 "LAPA": [{"id": "c", "version": "3"}, {"id": "d", "version": "5"}], "NOVO": [{"id": "e"}]}
    versoes = {"a": "10", "b": "6", "c": "3", "d": "5"}
    assert sorted(s.hoteis_que_mudaram(por_hotel, versoes, completa=False)) == ["BAHIA", "NOVO"]
    assert sorted(s.hoteis_que_mudaram(por_hotel, versoes, completa=True)) == sorted(por_hotel)
