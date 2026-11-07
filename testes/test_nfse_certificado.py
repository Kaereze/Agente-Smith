"""Certificado A1: abrir, CNPJ, validade, finalidade. Usa certificado FALSO fabricado na hora."""
import datetime

import apoio_nfse
import pytest
from apoio_nfse import CNPJ_TESTE, SENHA_TESTE, fabricar_pfx

from nfse import certificado


def _niveis(itens):
    return [i.nivel for i in itens]


def test_carrega_e_acha_o_cnpj(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx")
    cert = certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE)
    assert cert.cnpj == CNPJ_TESTE
    assert cert.nome == "HOTEL EXEMPLO LTDA"
    assert "senha" not in repr(cert).lower() and "PRIVATE" not in repr(cert)


def test_acha_o_cnpj_pelo_cn_quando_nao_tem_o_campo_oficial(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx", com_oid_cnpj=False)
    assert certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE).cnpj == CNPJ_TESTE


def test_senha_errada_nao_vaza_a_senha(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx")
    with pytest.raises(certificado.CertificadoInvalido) as erro:
        certificado.carregar(tmp_path / "a.pfx", "outra-senha-secreta")
    assert "outra-senha-secreta" not in str(erro.value)


def test_arquivo_inexistente_ou_lixo(tmp_path):
    with pytest.raises(certificado.CertificadoInvalido):
        certificado.carregar(tmp_path / "nao_existe.pfx", "x")
    (tmp_path / "lixo.pfx").write_bytes(b"isto nao e um certificado")
    with pytest.raises(certificado.CertificadoInvalido):
        certificado.carregar(tmp_path / "lixo.pfx", "x")


def test_diagnostico_tudo_certo(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx")
    cert = certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE)
    itens = certificado.diagnostico(cert, cnpj_esperado="11.222.333/0001-81")
    assert "erro" not in _niveis(itens) and "aviso" not in _niveis(itens)


def test_diagnostico_vencido_e_prestes_a_vencer(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx", dias=10)
    cert = certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE)
    assert "aviso" in _niveis(certificado.diagnostico(cert))
    depois = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    assert "erro" in _niveis(certificado.diagnostico(cert, agora=depois))


def test_diagnostico_sem_autenticacao_do_cliente_e_cnpj_diferente(tmp_path):
    fabricar_pfx(tmp_path / "a.pfx", cliente_auth=False)
    cert = certificado.carregar(tmp_path / "a.pfx", SENHA_TESTE)
    # sem a lista de finalidades vira aviso; com a lista sem clientAuth seria erro (coberto pelo certificado abaixo)
    assert "aviso" in _niveis(certificado.diagnostico(cert))
    assert "erro" in _niveis(certificado.diagnostico(cert, cnpj_esperado="00000000000192"))
    assert "aviso" in _niveis(certificado.diagnostico(cert, cnpj_esperado="11222333000263"))   # mesma raiz, outra filial


def test_diagnostico_finalidade_errada_e_erro(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"X:{CNPJ_TESTE}")])
    agora = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key()).serial_number(1)
         .not_valid_before(agora - datetime.timedelta(days=1)).not_valid_after(agora + datetime.timedelta(days=300))
         .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False).sign(chave, hashes.SHA256()))
    cert = certificado.Certificado(chave_privada=chave, certificado=c, cnpj=CNPJ_TESTE, nome="X", valido_de=c.not_valid_before_utc,
                                   valido_ate=c.not_valid_after_utc)
    assert "erro" in _niveis(certificado.diagnostico(cert))


def test_o_apoio_so_usa_cnpj_de_exemplo():
    assert apoio_nfse.CNPJ_TESTE == "11222333000181"
