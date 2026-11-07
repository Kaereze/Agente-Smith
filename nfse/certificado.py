"""Certificado digital A1 (.pfx/.p12): carregar, conferir validade, CNPJ e finalidade.

A senha entra só como argumento de `carregar` (vinda de variável de ambiente ou digitada no terminal, ver
primeiro_teste.py). Ela não é guardada em lugar nenhum e não aparece em print, log nem mensagem de erro.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OID_CNPJ_ICP_BRASIL = x509.ObjectIdentifier("2.16.76.1.3.3")     # pessoa jurídica: CNPJ no SubjectAlternativeName
AVISO_VENCIMENTO_DIAS = 30


class CertificadoInvalido(Exception):
    """Arquivo ilegível, senha errada ou sem chave privada. A mensagem nunca traz a senha."""


@dataclass
class Certificado:
    chave_privada: object = field(repr=False)
    certificado: x509.Certificate = field(repr=False)
    cadeia: list = field(default_factory=list, repr=False)
    cnpj: str = ""
    nome: str = ""
    valido_de: datetime = None
    valido_ate: datetime = None


@dataclass
class Item:
    nivel: str            # "ok", "aviso" ou "erro"
    texto: str


def _conteudo_der(valor):
    """Tira o cabeçalho DER (tipo + tamanho) de um valor simples e devolve o texto."""
    if len(valor) < 2:
        return ""
    tamanho = valor[1]
    inicio = 2
    if tamanho & 0x80:
        inicio += tamanho & 0x7F
    return valor[inicio:].decode("utf-8", errors="ignore")


def cnpj_do_certificado(cert):
    """CNPJ de 14 caracteres. Primeiro pelo campo oficial da ICP-Brasil (OID 2.16.76.1.3.3), depois pelo CN ('RAZAO:CNPJ')."""
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for outro in san.get_values_for_type(x509.OtherName):
            if outro.type_id == OID_CNPJ_ICP_BRASIL:
                achado = re.sub(r"[^0-9A-Za-z]", "", _conteudo_der(outro.value)).upper()
                if len(achado) == 14:
                    return achado
    except x509.ExtensionNotFound:
        pass
    cn = next((a.value for a in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)), "")
    achou = re.search(r":\s*([0-9A-Za-z]{14})\s*$", cn)
    return achou.group(1).upper() if achou else ""


def _nome(cert):
    cn = next((a.value for a in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)), "")
    return cn.split(":")[0].strip()


def carregar(caminho, senha):
    """Abre o .pfx/.p12. `senha` é str ou bytes. Erro vira CertificadoInvalido sem repetir a senha."""
    try:
        with open(caminho, "rb") as f:
            dados = f.read()
    except OSError as erro:
        raise CertificadoInvalido(f"não consegui abrir o arquivo do certificado ({erro.__class__.__name__})") from None
    if isinstance(senha, str):
        senha = senha.encode("utf-8")
    try:
        chave, cert, adicionais = pkcs12.load_key_and_certificates(dados, senha or None)
    except (ValueError, TypeError):
        raise CertificadoInvalido("senha errada ou arquivo de certificado inválido") from None
    if cert is None or chave is None:
        raise CertificadoInvalido("o arquivo não tem certificado com chave privada")
    return Certificado(chave_privada=chave, certificado=cert, cadeia=list(adicionais or []), cnpj=cnpj_do_certificado(cert),
                       nome=_nome(cert), valido_de=cert.not_valid_before_utc, valido_ate=cert.not_valid_after_utc)


def diagnostico(cert, agora=None, cnpj_esperado=None):
    """Lista de conferências do checklist do primeiro teste. `cnpj_esperado` = CNPJ do hotel (só números/letras)."""
    agora = agora or datetime.now(timezone.utc)
    itens = []
    if agora < cert.valido_de:
        itens.append(Item("erro", f"certificado ainda não vale (começa em {cert.valido_de:%d/%m/%Y})"))
    elif agora > cert.valido_ate:
        itens.append(Item("erro", f"certificado VENCIDO em {cert.valido_ate:%d/%m/%Y}"))
    elif cert.valido_ate - agora < timedelta(days=AVISO_VENCIMENTO_DIAS):
        itens.append(Item("aviso", f"vence em {(cert.valido_ate - agora).days} dias ({cert.valido_ate:%d/%m/%Y})"))
    else:
        itens.append(Item("ok", f"válido até {cert.valido_ate:%d/%m/%Y}"))

    if cert.cnpj:
        itens.append(Item("ok", f"CNPJ do certificado: {cert.cnpj[:2]}.{cert.cnpj[2:5]}.{cert.cnpj[5:8]}/{cert.cnpj[8:12]}-{cert.cnpj[12:]}"))
        if cnpj_esperado:
            esperado = re.sub(r"[^0-9A-Za-z]", "", cnpj_esperado).upper()
            if esperado == cert.cnpj:
                itens.append(Item("ok", "CNPJ do certificado = CNPJ do hotel"))
            elif esperado[:8] == cert.cnpj[:8]:
                itens.append(Item("aviso", "mesma raiz de CNPJ, mas é outra filial: o Emissor só aceita se houver procuração"))
            else:
                itens.append(Item("erro", "CNPJ do certificado é diferente do CNPJ do hotel"))
    else:
        itens.append(Item("aviso", "não achei o CNPJ dentro do certificado (pode ser certificado de pessoa física)"))

    try:
        usos = cert.certificado.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH in usos:
            itens.append(Item("ok", "tem a finalidade 'Autenticação do Cliente' (obrigatória)"))
        else:
            itens.append(Item("erro", "NÃO tem 'Autenticação do Cliente': o governo vai recusar a conexão"))
    except x509.ExtensionNotFound:
        itens.append(Item("aviso", "certificado sem lista de finalidades; só o teste de conexão mostra se serve"))

    if isinstance(cert.chave_privada, rsa.RSAPrivateKey):
        itens.append(Item("ok" if cert.chave_privada.key_size >= 2048 else "aviso", f"chave RSA de {cert.chave_privada.key_size} bits"))
    else:
        itens.append(Item("aviso", "a chave não é RSA; a assinatura deste programa só foi escrita para RSA"))
    return itens
