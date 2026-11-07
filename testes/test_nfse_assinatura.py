"""Assinatura XMLDSIG: assina, confere, e pega adulteração. Certificado FALSO."""
import datetime
from decimal import Decimal

import pytest
from apoio_nfse import SENHA_TESTE, fabricar_pfx

from nfse import assinatura, certificado, dps


@pytest.fixture
def cert(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx")
    return certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE)


def _dados():
    return dps.DadosDPS(prestador_cnpj="11222333000181", cod_municipio="2611606", serie="1", n_dps=7,
                        dh_emi=datetime.datetime(2026, 11, 7, 10, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3))),
                        competencia=datetime.date(2026, 11, 7), tomador_doc="11144477735", tomador_nome="MARCOS EXEMPLO & FILHOS",
                        descricao="HOSPEDAGEM 2 DIARIAS - VALOR DA DIARIA: R$ 100,00 <teste>", valor=Decimal("200.00"), cod_trib_mun="501")


@pytest.mark.parametrize("algoritmo", ["sha256", "sha1"])
def test_assina_e_confere(cert, algoritmo):
    d = _dados()
    assinado = assinatura.assinar(dps.montar_dps(d), dps.id_da_dps(d), cert, algoritmo)
    ok, motivo = assinatura.verificar(assinado)
    assert ok, motivo
    assert assinado.count("<Signature ") == 1 and assinado.rstrip().endswith("</DPS>")


def test_mudou_o_conteudo_depois_de_assinar_nao_confere(cert):
    d = _dados()
    assinado = assinatura.assinar(dps.montar_dps(d), dps.id_da_dps(d), cert)
    adulterado = assinado.replace("<vServ>200.00</vServ>", "<vServ>20000.00</vServ>")
    assert adulterado != assinado
    ok, motivo = assinatura.verificar(adulterado)
    assert not ok and "resumo" in motivo


def test_trocar_o_valor_da_assinatura_nao_confere(cert):
    d = _dados()
    assinado = assinatura.assinar(dps.montar_dps(d), dps.id_da_dps(d), cert)
    inicio = assinado.index("<SignatureValue>") + len("<SignatureValue>")
    trocado = assinado[:inicio] + ("A" if assinado[inicio] != "A" else "B") + assinado[inicio + 1:]
    assert not assinatura.verificar(trocado)[0]


def test_nao_assina_duas_vezes_nem_id_inexistente_nem_algoritmo_estranho(cert):
    d = _dados()
    xml = dps.montar_dps(d)
    assinado = assinatura.assinar(xml, dps.id_da_dps(d), cert)
    with pytest.raises(assinatura.ErroAssinatura):
        assinatura.assinar(assinado, dps.id_da_dps(d), cert)
    with pytest.raises(assinatura.ErroAssinatura):
        assinatura.assinar(xml, "DPS_QUE_NAO_EXISTE", cert)
    with pytest.raises(assinatura.ErroAssinatura):
        assinatura.assinar(xml, dps.id_da_dps(d), cert, "md5")


def test_canonicalizacao_igual_a_do_lxml(cert):
    """Confere a nossa C14N contra uma implementação independente (lxml), se estiver instalada.

    Compara o infDPS e o SignedInfo isolados (é assim que a nossa conta é feita). Não usa o c14n de SUBÁRVORE do lxml
    2.14.x/libxml2: ele põe xmlns="" à toa nos filhos (defeito conhecido), então o 'oráculo' seria errado.
    """
    etree = pytest.importorskip("lxml.etree")
    import xml.etree.ElementTree as ET
    d = _dados()
    xml = dps.montar_dps(d)
    assinado = assinatura.assinar(xml, dps.id_da_dps(d), cert)
    inf = ET.fromstring(assinado).find(f"{{{dps.NS_NFSE}}}infDPS")
    ET.register_namespace("", dps.NS_NFSE)
    isolado = ET.tostring(inf, encoding="unicode")
    assert assinatura._canonico(inf, dps.NS_NFSE) == etree.tostring(etree.fromstring(isolado.encode()), method="c14n")
    # documento inteiro (sem assinatura): a biblioteca padrão e o lxml têm de concordar byte a byte
    assert ET.canonicalize(xml, strip_text=False).encode() == etree.tostring(etree.fromstring(xml.encode()), method="c14n")
    si = ET.fromstring(assinado).find(f".//{{{assinatura.NS_DSIG}}}SignedInfo")
    ET.register_namespace("", assinatura.NS_DSIG)
    isolado = ET.tostring(si, encoding="unicode")
    assert assinatura._canonico(si, assinatura.NS_DSIG) == etree.tostring(etree.fromstring(isolado.encode()), method="c14n")
