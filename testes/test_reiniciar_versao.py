import atualizador

OK = {"atras": 0, "frente": 0, "limpo": True, "erro": ""}


def test_reinicia_quando_pasta_esta_na_frente_do_que_roda():
    assert atualizador.precisa_reiniciar(OK, "aa7624d 14/10", "29267a6")


def test_nao_reinicia_quando_ja_roda_a_versao_da_pasta():
    assert not atualizador.precisa_reiniciar(OK, "29267a6", "29267a6c0ffee")


def test_nao_reinicia_sem_versao_ou_com_erro_ou_atrasado():
    assert not atualizador.precisa_reiniciar(OK, "", "29267a6")
    assert not atualizador.precisa_reiniciar(OK, "aa7624d", "")
    assert not atualizador.precisa_reiniciar(dict(OK, erro="sem rede"), "aa7624d", "29267a6")
    assert not atualizador.precisa_reiniciar(dict(OK, atras=2), "aa7624d", "29267a6")
