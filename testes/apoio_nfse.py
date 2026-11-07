"""Apoio dos testes do pacote nfse: põe a raiz do projeto no caminho e fabrica um certificado FALSO (autoassinado).

Tudo inventado: CNPJ 11.222.333/0001-81, senha de teste, nenhum arquivo de certificado de verdade.
"""
import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from cryptography import x509                                                     # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization                  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa                         # noqa: E402
from cryptography.hazmat.primitives.serialization import pkcs12                   # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID                    # noqa: E402

CNPJ_TESTE = "11222333000181"
SENHA_TESTE = "senha-de-teste"


def _der_printable(texto):
    dados = texto.encode()
    return bytes([0x13, len(dados)]) + dados


def fabricar_pfx(caminho, dias=365, cliente_auth=True, com_oid_cnpj=True, comeca_em=None):
    """Grava um .pfx falso em `caminho` e devolve (chave, certificado)."""
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"HOTEL EXEMPLO LTDA:{CNPJ_TESTE}")])
    inicio = comeca_em or (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
    b = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(inicio).not_valid_after(inicio + datetime.timedelta(days=dias)))
    if com_oid_cnpj:
        outro = x509.OtherName(x509.ObjectIdentifier("2.16.76.1.3.3"), _der_printable(CNPJ_TESTE))
        b = b.add_extension(x509.SubjectAlternativeName([outro]), critical=False)
    if cliente_auth:
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    cert = b.sign(chave, hashes.SHA256())
    pfx = pkcs12.serialize_key_and_certificates(b"hotel", chave, cert, None, serialization.BestAvailableEncryption(SENHA_TESTE.encode()))
    with open(caminho, "wb") as f:
        f.write(pfx)
    return chave, cert
