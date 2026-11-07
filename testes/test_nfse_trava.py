"""A trava de ambiente do pacote nfse: só produção restrita, nunca produção de verdade."""
import apoio_nfse  # noqa: F401  (põe a raiz do projeto no caminho)
import pytest

from nfse import trava


@pytest.mark.parametrize("url", [
    "https://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse",
    "https://adn.producaorestrita.nfse.gov.br/parametrizacao/2611606/convenio",
    "https://SEFIN.producaorestrita.nfse.gov.br:443/SefinNacional/dps/x",
])
def test_urls_de_teste_passam(url):
    assert trava.validar_url(url) == url


@pytest.mark.parametrize("url", [
    "https://sefin.nfse.gov.br/SefinNacional/nfse",                      # produção de verdade
    "https://adn.nfse.gov.br/contribuintes/DFe/1",
    "http://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse",      # sem TLS
    "https://sefin.producaorestrita.nfse.gov.br.mal.com/x",              # domínio parecido
    "https://mal.com/sefin.producaorestrita.nfse.gov.br",
    "https://usuario:senha@sefin.producaorestrita.nfse.gov.br/x",
    "https://sefin.producaorestrita.nfse.gov.br:8443/x",
    "ftp://sefin.producaorestrita.nfse.gov.br/x",
    "",
])
def test_urls_proibidas_sao_barradas(url):
    with pytest.raises(trava.AmbienteProibido):
        trava.validar_url(url)


def test_xml_so_sai_com_tpamb_2():
    assert trava.validar_xml_de_teste("<DPS><infDPS><tpAmb>2</tpAmb></infDPS></DPS>")
    for xml in ("<DPS><tpAmb>1</tpAmb></DPS>", "<DPS></DPS>", "<DPS><tpAmb>9</tpAmb></DPS>"):
        with pytest.raises(trava.AmbienteProibido):
            trava.validar_xml_de_teste(xml)


def test_resposta_de_producao_para_tudo():
    assert trava.validar_resposta({"tipoAmbiente": 2, "idDps": "x"})
    assert trava.validar_resposta({"sem_campo": 1}) == {"sem_campo": 1}
    assert trava.validar_resposta(None) is None
    with pytest.raises(trava.AmbienteProibido):
        trava.validar_resposta({"tipoAmbiente": 1})


def test_nao_existe_atalho_para_liberar_producao():
    """Nenhuma variável de ambiente muda os hosts permitidos."""
    import os
    os.environ["NFSE_PRODUCAO"] = "1"
    try:
        with pytest.raises(trava.AmbienteProibido):
            trava.validar_url("https://sefin.nfse.gov.br/SefinNacional/nfse")
    finally:
        del os.environ["NFSE_PRODUCAO"]
