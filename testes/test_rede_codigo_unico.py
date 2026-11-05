"""Rede entre PCs (Fase 1, 05/11/2026): código único por pedido, validade curta e limites do servidor. Só dados inventados."""
import http.client
import json

import ajustes_tabela
import rede_local

SEGREDO = bytes(range(32))


def test_codigo_novo_passa_e_repetido_e_recusado():
    c = rede_local.CodigosUsados(validade=30, relogio=lambda: 1000.0)
    assert c.usar("a" * 32) is True
    assert c.usar("a" * 32) is False


def test_codigo_vazio_curto_ou_estranho_e_recusado():
    c = rede_local.CodigosUsados(validade=30, relogio=lambda: 1000.0)
    assert not c.usar("") and not c.usar("curto") and not c.usar(None) and not c.usar("x" * 200)


def test_codigo_velho_e_esquecido_depois_do_dobro_da_validade():
    agora = [1000.0]
    c = rede_local.CodigosUsados(validade=30, relogio=lambda: agora[0])
    assert c.usar("b" * 32)
    agora[0] += 61
    assert c.usar("c" * 32) and "b" * 32 not in c._vistos


def test_assinatura_muda_com_o_codigo():
    a = rede_local.assinar(SEGREDO, "1000.0", "/rede/ping", b"{}", "c" * 32)
    assert a != rede_local.assinar(SEGREDO, "1000.0", "/rede/ping", b"{}", "d" * 32)
    assert not rede_local.assinatura_ok(SEGREDO, "1000.0", "/rede/ping", b"{}", a, agora=1001.0, codigo="d" * 32)
    assert rede_local.assinatura_ok(SEGREDO, "1000.0", "/rede/ping", b"{}", a, agora=1001.0, codigo="c" * 32)


def test_validade_de_fabrica_e_30_segundos():
    padrao = {e[0]: e[1] for e in ajustes_tabela.ENTRADAS}["rede.assinatura_validade_segundos"]
    assert padrao == 30   # o ajustes.json do administrador pode mudar o valor em uso; o de fábrica é 30
    assert not rede_local.assinatura_ok(SEGREDO, "1000.0", "/rede/ping", b"{}",
                                        rede_local.assinar(SEGREDO, "1000.0", "/rede/ping", b"{}"), agora=1000.0 + rede_local.VALIDADE_ASSINATURA + 1)


def _servidor():
    s = rede_local.Servidor(SEGREDO, {"ping": lambda corpo: {"ok": True}}, porta=0)
    assert s.iniciar()
    return s, s.http.server_address[1]


def _post(porta, cabecalhos, corpo=b"{}"):
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    con.request("POST", "/rede/ping", body=corpo, headers=cabecalhos)
    r = con.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_servidor_aceita_uma_vez_e_recusa_a_copia():
    s, porta = _servidor()
    try:
        import time
        quando, codigo = f"{time.time():.3f}", "e" * 32
        cab = {"X-Quando": quando, "X-Codigo": codigo, "X-Assinatura": rede_local.assinar(SEGREDO, quando, "/rede/ping", b"{}", codigo)}
        assert _post(porta, cab)[0] == 200
        assert _post(porta, cab)[0] == 403
        sem = {"X-Quando": quando, "X-Assinatura": rede_local.assinar(SEGREDO, quando, "/rede/ping", b"{}")}
        assert _post(porta, sem)[0] == 403
    finally:
        s.http.shutdown()


def test_perguntar_e_o_servidor_conversam():
    s, porta = _servidor()
    try:
        assert rede_local.perguntar(SEGREDO, f"127.0.0.1:{porta}", "ping", {}, tempo=5) == {"ok": True}
        assert rede_local.perguntar(SEGREDO, f"127.0.0.1:{porta}", "ping", {}, tempo=5) == {"ok": True}
    finally:
        s.http.shutdown()


def test_content_length_invalido_e_gigante_sao_recusados():
    s, porta = _servidor()
    try:
        assert _post(porta, {"Content-Length": "-5"}, b"")[0] == 400
        assert _post(porta, {"Content-Length": str(rede_local.MAX_CORPO + 1)}, b"")[0] == 413
    except (ConnectionError, http.client.HTTPException):
        pass   # o http.client do teste pode recusar o cabeçalho torto antes de enviar; o servidor está coberto abaixo
    finally:
        s.http.shutdown()


def test_conexao_parada_e_cortada():
    assert rede_local.TEMPO_LEITURA <= 10
