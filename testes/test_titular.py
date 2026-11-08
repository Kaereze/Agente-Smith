"""Pedido do titular (LGPD, 08/11/2026): localizar e apagar os dados de uma pessoa neste PC, sem mostrar conteúdo."""
import pytest

import armazem
import indice_emails
import titular

CPF = "529.982.247-25"   # inventado (dígitos válidos)


def _email(i, de="ana@exemplo.com", texto=""):
    return {"id": f"id{i}", "entry": f"e{i}", "pasta": "entrada", "caixa": "nf@hotel.com", "hotel": "BAHIA", "de": de, "nome": "Ana Exemplo",
            "para": "nf@hotel.com", "assunto": "Nota fiscal", "quando": "2026-11-01T10:00:00", "previa": "", "anexos": [], "texto": texto, "completo": 1}


@pytest.fixture
def indice(tmp_path):
    ind = indice_emails.Indice(tmp_path / "i.sqlite")
    ind.gravar([_email(1, texto=f"Segue o CPF {CPF} para a nota"), _email(2, de="outra@exemplo.com", texto="sem dado"), _email(3, texto="CPF 52998224725 de novo")])
    return ind


def test_termos_de_cpf_cnpj_email_e_nome():
    assert titular.termos("529.982.247-25") == ["52998224725", "529.982.247-25"]
    assert titular.termos("11222333000181") == ["11222333000181", "11.222.333/0001-81"]
    assert titular.termos("Ana@Exemplo.com") == ["ana@exemplo.com"]
    assert titular.termos("Maria Souza") == ["maria souza"] and titular.termos("") == []


def test_localizar_acha_pelo_cpf_nas_duas_formas_e_so_conta(indice, monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    (tmp_path / "nf_achadas.json").write_text(f'{{"a": {{"doc": "{CPF}"}}, "b": {{"doc": "00000000000"}}}}', encoding="utf-8")
    achados = titular.localizar(CPF, indice=indice)
    assert achados == {"indice_emails.sqlite": 2, "nf_achadas.json": 1}
    assert all(isinstance(v, int) for v in achados.values())


def test_apagar_do_indice_tira_so_os_dessa_pessoa(indice):
    assert titular.apagar_do_indice(CPF, indice=indice) == 2
    assert indice.total() == 1 and titular.localizar(CPF, indice=indice) == {}


def test_apagar_cache_so_vale_para_cache_reconstruivel_com_dado_pessoal(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    (tmp_path / "cache_textos_nf.json").write_text("{}", encoding="utf-8")
    assert titular.apagar_arquivo("cache_textos_nf.json") is True and not (tmp_path / "cache_textos_nf.json").exists()
    assert titular.apagar_arquivo("cache_textos_nf.json") is False   # já não existe
    for proibido in ("app.json", "maquina.json", "indice_emails.sqlite", "acessos", "nao_existe.json"):
        with pytest.raises(ValueError):
            titular.apagar_arquivo(proibido)
