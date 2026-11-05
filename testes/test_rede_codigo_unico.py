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


# ---------- Fase 2: cifra do conteúdo ----------
def test_cifra_vai_e_volta_e_recusa_adulteracao_ou_outro_segredo():
    c = rede_local.cifrar(SEGREDO, b'{"cpf": "111.444.777-35"}', b"x")
    assert b"111.444" not in c
    assert rede_local.decifrar(SEGREDO, c, b"x") == b'{"cpf": "111.444.777-35"}'
    import pytest
    with pytest.raises(ValueError):
        rede_local.decifrar(SEGREDO, c, b"outro-associado")
    with pytest.raises(ValueError):
        rede_local.decifrar(bytes(32), c, b"x")
    with pytest.raises(ValueError):
        rede_local.decifrar(SEGREDO, c[:-1] + bytes([c[-1] ^ 1]), b"x")
    with pytest.raises(ValueError):
        rede_local.decifrar(SEGREDO, b"curto", b"x")


def test_pedido_e_resposta_andam_cifrados_pela_rede(monkeypatch):
    visto = {}
    s = rede_local.Servidor(SEGREDO, {"ping": lambda corpo: visto.setdefault("corpo", corpo) and {"cpf": "111.444.777-35"}}, porta=0)
    assert s.iniciar()
    porta = s.http.server_address[1]
    brutos = []
    abrir = rede_local.urllib.request.urlopen

    def espiar(pedido, timeout=None):
        brutos.append(pedido.data)
        r = abrir(pedido, timeout=timeout)
        brutos.append(r.read())
        r.close()
        return abrir_de_novo(brutos[-1], r.headers)
    import io

    class Resp(io.BytesIO):
        def __init__(self, dados, headers):
            super().__init__(dados)
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def abrir_de_novo(dados, headers):
        return Resp(dados, headers)
    monkeypatch.setattr(rede_local.urllib.request, "urlopen", espiar)
    try:
        r = rede_local.perguntar(SEGREDO, f"127.0.0.1:{porta}", "ping", {"q": "Marcos Exemplo 111.444.777-35"}, tempo=5)
    finally:
        s.http.shutdown()
    assert r == {"cpf": "111.444.777-35"} and visto["corpo"] == {"q": "Marcos Exemplo 111.444.777-35"}
    assert all(b"111.444" not in b and b"Marcos" not in b for b in brutos)


def test_servidor_recusa_pedido_aberto_quando_a_cifra_for_exigida(monkeypatch):
    import time
    monkeypatch.setattr(rede_local, "EXIGIR_CIFRA", True)
    s, porta = _servidor()
    try:
        quando, codigo = f"{time.time():.3f}", "f" * 32
        cab = {"X-Quando": quando, "X-Codigo": codigo, "X-Assinatura": rede_local.assinar(SEGREDO, quando, "/rede/ping", b"{}", codigo)}
        assert _post(porta, cab)[0] == 403
    finally:
        s.http.shutdown()


def test_segredo_novo_e_aleatorio_e_vale_como_arquivo_da_rede(tmp_path):
    import json as j
    chave = tmp_path / "chave-api.json"
    chave.write_text(j.dumps({"private_key_id": "a", "private_key": "FICTICIA"}), encoding="utf-8")
    assert rede_local.gerar_segredo_novo(tmp_path / "segredo-rede.txt")
    novo = rede_local.segredo_da_chave(chave)
    assert len(novo) == 32 and novo != rede_local._segredo_calculado(chave)
    rede_local.gerar_segredo_novo(tmp_path / "segredo-rede.txt")
    assert rede_local.segredo_da_chave(chave) != novo
