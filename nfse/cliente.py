"""Cliente HTTP com autenticação mútua (certificado A1) para a produção restrita da NFS-e Nacional.

Regras (RN-80 a RN-83):
- POST (emissão e evento) NUNCA é repetido sozinho: se der erro de rede no meio, a nota pode ter sido criada. Quem chama
  consulta pelo Id da DPS antes de decidir qualquer coisa.
- Consulta (GET/HEAD) pode repetir no máximo 2 vezes, só em falha de rede ou erro 5xx. 404 é resposta, não falha:
  significa "não existe".
- Não segue redirecionamento (poderia levar para fora da produção restrita).
- Toda URL passa por `trava.validar_url`; toda resposta com tipoAmbiente passa por `trava.validar_resposta`.
- A chave privada vai para um arquivo temporário protegido por senha aleatória só o tempo de abrir a conexão, e o arquivo
  é apagado logo depois. Nada de certificado ou senha em log.
"""
import base64
import gzip
import json
import os
import secrets
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization

from . import trava

SEFIN = "https://sefin.producaorestrita.nfse.gov.br/SefinNacional"
ADN_PARAMETROS = "https://adn.producaorestrita.nfse.gov.br/parametrizacao"
ADN_CONTRIBUINTE = "https://adn.producaorestrita.nfse.gov.br/contribuintes"
TEMPO_LIMITE = 30
TENTATIVAS_CONSULTA = 3          # 1 + até 2 repetições


@dataclass
class Resposta:
    status: int
    texto: str
    json: object = None


class ErroRede(Exception):
    pass


def compactar(xml):
    """XML (str) -> gzip -> base64 (str), como a API pede."""
    return base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode("ascii")


def descompactar(b64):
    """base64 -> gzip -> XML (str)."""
    return gzip.decompress(base64.b64decode(b64)).decode("utf-8")


class _SemRedirecionamento(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ErroRede(f"o servidor mandou redirecionar (HTTP {code}); por segurança não sigo")


def contexto_ssl(certificado):
    """Contexto TLS 1.2+ com o certificado do hotel. Usa arquivos temporários que somem logo em seguida."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_default_certs()
    senha_temp = secrets.token_hex(16).encode()
    pem_cert = certificado.certificado.public_bytes(serialization.Encoding.PEM)
    for extra in certificado.cadeia:
        pem_cert += extra.public_bytes(serialization.Encoding.PEM)
    pem_chave = certificado.chave_privada.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                        serialization.BestAvailableEncryption(senha_temp))
    with tempfile.TemporaryDirectory(prefix="nfse_") as pasta:
        arq_cert, arq_chave = os.path.join(pasta, "c.pem"), os.path.join(pasta, "k.pem")
        for caminho, dados in ((arq_cert, pem_cert), (arq_chave, pem_chave)):
            with open(caminho, "wb") as f:
                f.write(dados)
        ctx.load_cert_chain(arq_cert, arq_chave, password=senha_temp)
    return ctx


class Cliente:
    def __init__(self, certificado=None, contexto=None, abrir=None):
        """`abrir` existe só para os testes trocarem a rede por um dublê."""
        self._abrir = abrir
        if abrir is None:
            ctx = contexto or contexto_ssl(certificado)
            self._abrir = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _SemRedirecionamento()).open

    def _uma_vez(self, metodo, url, corpo):
        trava.validar_url(url)
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        req = urllib.request.Request(url, data=dados, method=metodo,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
        try:
            with self._abrir(req, timeout=TEMPO_LIMITE) as r:
                status, texto = r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as erro:      # 4xx/5xx também trazem corpo com a explicação do governo
            status, texto = erro.code, erro.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ConnectionError, OSError) as erro:
            raise ErroRede(f"falha de rede ({erro.__class__.__name__}): {getattr(erro, 'reason', erro)}") from None
        try:
            corpo_json = json.loads(texto) if texto.strip() else None
        except ValueError:
            corpo_json = None
        trava.validar_resposta(corpo_json)
        return Resposta(status, texto, corpo_json)

    def consultar(self, metodo, url):
        """GET ou HEAD. Repete até 2 vezes em falha de rede ou 5xx."""
        if metodo not in ("GET", "HEAD"):
            raise ValueError("consultar() é só para GET/HEAD")
        ultimo = None
        for tentativa in range(TENTATIVAS_CONSULTA):
            try:
                r = self._uma_vez(metodo, url, None)
                if r.status < 500:
                    return r
                ultimo = r
            except ErroRede as erro:
                ultimo = erro
            if tentativa < TENTATIVAS_CONSULTA - 1:
                time.sleep(2 * (tentativa + 1))
        if isinstance(ultimo, Resposta):
            return ultimo
        raise ultimo

    def enviar(self, url, corpo):
        """POST. Uma única tentativa, sempre."""
        return self._uma_vez("POST", url, corpo)
