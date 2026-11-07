"""O programa do primeiro teste: etapas offline e as travas de segurança do 'emitir'. Nada sai pela rede."""
import os
import shutil

import apoio_nfse  # noqa: F401
import pytest
from apoio_nfse import SENHA_TESTE, fabricar_pfx

from nfse import cliente, dps, primeiro_teste


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    fabricar_pfx(tmp_path / "hotel.pfx")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NFSE_CERT_SENHA", SENHA_TESTE)
    return tmp_path


def test_certificado_ok(ambiente, capsys):
    assert primeiro_teste.main(["certificado", "--pfx", str(ambiente / "hotel.pfx"), "--cnpj-hotel", "11222333000181"]) == 0
    saida = capsys.readouterr().out
    assert "pode seguir" in saida and SENHA_TESTE not in saida


def test_certificado_de_outro_cnpj_da_erro(ambiente, capsys):
    assert primeiro_teste.main(["certificado", "--pfx", str(ambiente / "hotel.pfx"), "--cnpj-hotel", "00000000000192"]) == 1
    assert "ERRO" in capsys.readouterr().out


def test_senha_errada_sai_sem_mostrar_a_senha(ambiente, monkeypatch, capsys):
    monkeypatch.setenv("NFSE_CERT_SENHA", "errada-123")
    with pytest.raises(SystemExit):
        primeiro_teste.main(["certificado", "--pfx", str(ambiente / "hotel.pfx")])
    assert "errada-123" not in capsys.readouterr().out


def test_assinatura_offline_gera_dois_arquivos_conferidos(ambiente, capsys):
    assert primeiro_teste.main(["assinatura", "--pfx", str(ambiente / "hotel.pfx")]) == 0
    saida = capsys.readouterr().out
    assert saida.count("OK ") == 2 and "ERRO" not in saida
    assert (ambiente / "saida_nfse_teste" / "dps_exemplo_sha256.xml").exists()
    assert (ambiente / "saida_nfse_teste" / "dps_exemplo_sha1.xml").exists()


def test_emitir_e_cancelar_exigem_xsd():
    for args in (["emitir", "--pfx", "x", "--dados", "y"], ["cancelar", "--pfx", "x", "--chave", "1", "--motivo", "m"]):
        with pytest.raises(SystemExit):
            primeiro_teste.montar_parser().parse_args(args)


def _preparar_emissao(ambiente, monkeypatch):
    shutil.copy(os.path.join(apoio_nfse.RAIZ, "nfse", "exemplo_dados_teste.json"), ambiente / "dados.json")
    monkeypatch.setattr(dps, "validar_xsd", lambda xml, caminho: [])           # XSD oficial ainda não está no projeto

    def nao_pode_abrir(*a, **k):
        raise AssertionError("tentou usar a rede")
    monkeypatch.setattr(cliente, "contexto_ssl", nao_pode_abrir)


def test_emitir_sem_digitar_a_confirmacao_nao_envia_nada(ambiente, monkeypatch, capsys):
    _preparar_emissao(ambiente, monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *_: "sim")
    assert primeiro_teste.main(["emitir", "--pfx", str(ambiente / "hotel.pfx"), "--dados", str(ambiente / "dados.json"),
                                "--xsd", "qualquer.xsd"]) == 0
    saida = capsys.readouterr().out
    assert "Nada foi enviado" in saida and "RESUMO PARA CONFERIR" in saida
    assert (ambiente / "saida_nfse_teste" / "dps_enviado.xml").exists()


def test_emitir_recusa_certificado_de_outro_cnpj(ambiente, monkeypatch, capsys):
    _preparar_emissao(ambiente, monkeypatch)
    texto = (ambiente / "dados.json").read_text(encoding="utf-8").replace("11222333000181", "12345678000195")
    (ambiente / "dados.json").write_text(texto, encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("não podia nem chegar na confirmação"))
    assert primeiro_teste.main(["emitir", "--pfx", str(ambiente / "hotel.pfx"), "--dados", str(ambiente / "dados.json"),
                                "--xsd", "qualquer.xsd"]) == 1
    assert "RECUSADO" in capsys.readouterr().out


def test_emitir_com_dado_ruim_para_antes_de_assinar(ambiente, monkeypatch, capsys):
    _preparar_emissao(ambiente, monkeypatch)
    texto = (ambiente / "dados.json").read_text(encoding="utf-8").replace("11144477735", "11144477736")
    (ambiente / "dados.json").write_text(texto, encoding="utf-8")
    assert primeiro_teste.main(["emitir", "--pfx", str(ambiente / "hotel.pfx"), "--dados", str(ambiente / "dados.json"),
                                "--xsd", "qualquer.xsd"]) == 1
    assert "DADOS COM PROBLEMA" in capsys.readouterr().out


def test_tabela_de_erros_cobre_os_codigos_do_swagger():
    for codigo in (200, 201, 400, 401, 403, 404, 500):
        assert codigo in primeiro_teste.TABELA_ERROS
