"""Validações de dados da NFS-e (CPF, CNPJ numérico e alfanumérico, dinheiro, datas, Id da DPS). Só números de exemplo."""
from datetime import date
from decimal import Decimal

import apoio_nfse  # noqa: F401
import pytest

from nfse.validacao import (cnpj_valido, cpf_valido, dinheiro, doc_tomador_valido, id_dps, total_nota, valor_diaria_estimado,
                            validar_estadia)


def test_cpf():
    assert cpf_valido("111.444.777-35") and cpf_valido("529.982.247-25")
    assert not cpf_valido("111.444.777-36") and not cpf_valido("111.111.111-11") and not cpf_valido("1234")


def test_cnpj_numerico_e_alfanumerico():
    assert cnpj_valido("11.222.333/0001-81") and not cnpj_valido("11.222.333/0001-82")
    assert cnpj_valido("12.ABC.345/01DE-35") and not cnpj_valido("12.ABC.345/01DE-34")   # exemplo publicado pela Receita
    assert cnpj_valido("12abc34501de35")


def test_documento_do_tomador():
    assert doc_tomador_valido("111.444.777-35") == (True, "CPF")
    assert doc_tomador_valido("11.222.333/0001-81") == (True, "CNPJ")
    assert doc_tomador_valido("123")[1] == "DESCONHECIDO"


def test_dinheiro_recusa_float_e_arredonda_para_cima_na_metade():
    with pytest.raises(TypeError):
        dinheiro(10.1)
    assert dinheiro("10.005") == Decimal("10.01") and dinheiro("204.29") == Decimal("204.29")


def test_estadia():
    assert validar_estadia(date(2026, 10, 13), date(2026, 10, 27), 14) == []
    assert validar_estadia(date(2026, 10, 13), date(2026, 10, 27), 13)
    assert validar_estadia(date(2026, 10, 27), date(2026, 10, 13), 14)


def test_total_e_diaria_estimada():
    assert total_nota("100.00", "10.50", "5.25") == Decimal("115.75")
    with pytest.raises(ValueError):
        total_nota("0", "0", "0")
    with pytest.raises(ValueError):
        total_nota("-1", "0", "5")
    assert valor_diaria_estimado("2860.06", 14) == Decimal("204.29")


def test_id_da_dps_tem_45_caracteres():
    ident = id_dps("2611606", "11.222.333/0001-81", "1", 7)
    assert ident == "DPS26116062" + "11222333000181" + "00001" + "000000000000007" and len(ident) == 45
    for ruim in (("26116", "11222333000181", "1", 7), ("2611606", "112", "1", 7), ("2611606", "11222333000181", "0", 7),
                 ("2611606", "11222333000181", "1", 0)):
        with pytest.raises(ValueError):
            id_dps(*ruim)
