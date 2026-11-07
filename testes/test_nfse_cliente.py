"""Cliente HTTP: regras de repetição, trava de endereço e compactação. A rede é trocada por um dublê (nada sai do PC)."""
import io
import urllib.error

import apoio_nfse  # noqa: F401
import pytest

from nfse import cliente, trava

URL = cliente.SEFIN + "/dps/DPS123"


class RespostaFalsa(io.BytesIO):
    def __init__(self, status, corpo=b""):
        super().__init__(corpo)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _cliente(*respostas):
    """Dublê de rede: devolve as respostas na ordem; um Exception é lançado em vez de devolvido."""
    chamadas = []
    fila = list(respostas)

    def abrir(req, timeout=None):
        chamadas.append((req.get_method(), req.full_url))
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        if item.status >= 400:
            raise urllib.error.HTTPError(req.full_url, item.status, "x", {}, io.BytesIO(item.getvalue()))
        return item

    c = cliente.Cliente(abrir=abrir)
    c.chamadas = chamadas
    return c


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(cliente.time, "sleep", lambda s: None)


def test_compactar_ida_e_volta():
    xml = "<a>ação & teste</a>"
    assert cliente.descompactar(cliente.compactar(xml)) == xml


def test_404_e_resposta_nao_falha_e_nao_repete():
    c = _cliente(RespostaFalsa(404, b'{"erro":{"codigo":"E404"}}'))
    r = c.consultar("GET", URL)
    assert r.status == 404 and r.json["erro"]["codigo"] == "E404" and len(c.chamadas) == 1


def test_consulta_repete_no_maximo_duas_vezes_em_falha_de_rede():
    c = _cliente(urllib.error.URLError("caiu"), urllib.error.URLError("caiu"), RespostaFalsa(200, b"{}"))
    assert c.consultar("GET", URL).status == 200 and len(c.chamadas) == 3
    c = _cliente(*[urllib.error.URLError("caiu")] * 3)
    with pytest.raises(cliente.ErroRede):
        c.consultar("GET", URL)
    assert len(c.chamadas) == 3


def test_consulta_repete_em_5xx_e_devolve_o_ultimo():
    c = _cliente(RespostaFalsa(500), RespostaFalsa(500), RespostaFalsa(503, b"{}"))
    assert c.consultar("GET", URL).status == 503 and len(c.chamadas) == 3


def test_post_nunca_repete():
    c = _cliente(urllib.error.URLError("caiu no meio"), RespostaFalsa(201, b"{}"))
    with pytest.raises(cliente.ErroRede):
        c.enviar(cliente.SEFIN + "/nfse", {"dpsXmlGZipB64": "x"})
    assert len(c.chamadas) == 1
    c = _cliente(RespostaFalsa(500, b"{}"))
    assert c.enviar(cliente.SEFIN + "/nfse", {"a": 1}).status == 500 and len(c.chamadas) == 1


def test_consultar_nao_aceita_post():
    with pytest.raises(ValueError):
        _cliente().consultar("POST", URL)


def test_endereco_fora_da_producao_restrita_nem_chega_na_rede():
    c = _cliente(RespostaFalsa(200, b"{}"))
    with pytest.raises(trava.AmbienteProibido):
        c.consultar("GET", "https://sefin.nfse.gov.br/SefinNacional/dps/x")
    assert c.chamadas == []


def test_resposta_dizendo_que_e_producao_para_tudo():
    c = _cliente(RespostaFalsa(200, b'{"tipoAmbiente":1}'))
    with pytest.raises(trava.AmbienteProibido):
        c.consultar("GET", URL)


def test_contexto_ssl_exige_tls12(tmp_path):
    from apoio_nfse import SENHA_TESTE, fabricar_pfx

    from nfse import certificado
    fabricar_pfx(tmp_path / "a.pfx")
    ctx = cliente.contexto_ssl(certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE))
    import ssl
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2 and ctx.verify_mode == ssl.CERT_REQUIRED
    assert not list(tmp_path.glob("*.pem")) and not list(tmp_path.glob("nfse_*"))
