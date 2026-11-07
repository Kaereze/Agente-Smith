"""Montagem do DPS e do pedido de cancelamento (rascunho até o XSD oficial entrar no projeto)."""
import datetime
import json
import xml.etree.ElementTree as ET
from decimal import Decimal

import apoio_nfse  # noqa: F401
import pytest

from nfse import dps, trava

FUSO = datetime.timezone(datetime.timedelta(hours=-3))


def _dados(**mudar):
    base = dict(prestador_cnpj="11222333000181", cod_municipio="2611606", serie="1", n_dps=7,
                dh_emi=datetime.datetime(2026, 11, 7, 10, 0, 0, tzinfo=FUSO), competencia=datetime.date(2026, 11, 7),
                tomador_doc="11144477735", tomador_nome="MARCOS EXEMPLO", descricao="HOSPEDAGEM 2 DIARIAS - VALOR DA DIARIA: R$ 100,00",
                valor=Decimal("200.00"), cod_trib_mun="501")
    base.update(mudar)
    return dps.DadosDPS(**base)


def test_monta_xml_bem_formado_de_teste_com_id_de_45():
    xml = dps.montar_dps(_dados())
    raiz = ET.fromstring(xml)
    inf = raiz.find(f"{{{dps.NS_NFSE}}}infDPS")
    assert inf.get("Id") == dps.id_da_dps(_dados()) and len(inf.get("Id")) == 45
    assert trava.validar_xml_de_teste(xml)            # tpAmb 2
    assert "<vServ>200.00</vServ>" in xml and "<cTribMun>501</cTribMun>" in xml and "<CPF>11144477735</CPF>" in xml


def test_escapa_texto_perigoso():
    xml = dps.montar_dps(_dados(tomador_nome="A & B <C>"))
    assert "A &amp; B &lt;C&gt;" in xml and ET.fromstring(xml) is not None


def test_sem_aliquota_nao_escreve_paliq():
    assert "<pAliq>" not in dps.montar_dps(_dados())
    assert "<pAliq>5.00</pAliq>" in dps.montar_dps(_dados(aliquota_iss=Decimal("5.00")))


def test_cnpj_como_tomador_usa_tag_cnpj():
    assert "<toma><CNPJ>11222333000181</CNPJ>" in dps.montar_dps(_dados(tomador_doc="11.222.333/0001-81"))


@pytest.mark.parametrize("mudar", [
    dict(prestador_cnpj="11222333000182"), dict(tomador_doc="11144477736"), dict(cod_municipio="26116"), dict(tomador_nome=" "),
    dict(descricao="curta"), dict(valor=Decimal("0")), dict(cod_trib_nac="9101"), dict(serie="0"), dict(n_dps=0),
    dict(dh_emi=datetime.datetime(2026, 11, 7, 10, 0, 0)),
])
def test_dado_ruim_nao_vira_xml(mudar):
    assert dps.problemas(_dados(**mudar))
    with pytest.raises(dps.DadosInvalidos):
        dps.montar_dps(_dados(**mudar))


def test_le_o_arquivo_de_exemplo():
    import os
    caminho = os.path.join(apoio_nfse.RAIZ, "nfse", "exemplo_dados_teste.json")
    dados = dps.de_json(caminho)
    assert dps.problemas(dados) == []
    assert "_aviso" in json.load(open(caminho, encoding="utf-8"))


CHAVE = "26116062" + "1" + "1" * 41      # 50 dígitos inventados


def test_pedido_de_cancelamento():
    xml = dps.montar_pedido_cancelamento(CHAVE, "11222333000181", "1", "Cancelamento de teste do primeiro ensaio",
                                         datetime.datetime(2026, 11, 7, 11, 0, 0, tzinfo=FUSO))
    inf = ET.fromstring(xml).find(f"{{{dps.NS_NFSE}}}infPedReg")
    assert inf.get("Id") == "PRE" + CHAVE + "101101" and len(inf.get("Id")) == 59
    assert trava.validar_xml_de_teste(xml)


@pytest.mark.parametrize("chave,cnpj,motivo", [("123", "11222333000181", "Cancelamento de teste do ensaio"),
                                                (CHAVE, "11222333000182", "Cancelamento de teste do ensaio"),
                                                (CHAVE, "11222333000181", "curto")])
def test_cancelamento_com_dado_ruim_e_barrado(chave, cnpj, motivo):
    with pytest.raises(dps.DadosInvalidos):
        dps.montar_pedido_cancelamento(chave, cnpj, "1", motivo, datetime.datetime(2026, 11, 7, tzinfo=FUSO))
