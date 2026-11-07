"""Assinatura XMLDSIG (enveloped) do DPS e do pedido de evento, só com a biblioteca padrão + `cryptography`.

Formato: <Signature> como irmã do elemento assinado (dentro da raiz), Reference ao Id do elemento, transforms
enveloped-signature + C14N inclusiva (REC-xml-c14n-20010315), certificado em X509Data.

P-19 (ABERTA): os documentos oficiais que temos não dizem se o governo aceita SHA-1, SHA-256 ou os dois. Por isso o
algoritmo é um parâmetro ("sha256" ou "sha1") e o primeiro teste experimenta (SHA-256 primeiro). O resultado vai para
o cofre e fecha a P-19. Não existe padrão "esperto": quem chama escolhe.

Premissa da canonicalização: o XML montado por `dps.py` só tem UM namespace (o padrão, na raiz). Por isso o elemento
assinado é canonicalizado sozinho, com esse namespace declarado nele. `verificar` refaz tudo do zero para provar.
"""
import base64
import hashlib
import xml.etree.ElementTree as ET

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
URI_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
URI_ENVELOPED = NS_DSIG + "enveloped-signature"
ALGORITMOS = {
    "sha256": {"hash": hashes.SHA256, "hashlib": hashlib.sha256,
               "assinatura": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256", "resumo": "http://www.w3.org/2001/04/xmlenc#sha256"},
    "sha1": {"hash": hashes.SHA1, "hashlib": hashlib.sha1,
             "assinatura": NS_DSIG + "rsa-sha1", "resumo": NS_DSIG + "sha1"},
}


class ErroAssinatura(Exception):
    pass


def _canonico(elemento, namespace):
    """C14N do elemento sozinho, com o namespace padrão declarado nele. Devolve bytes."""
    ET.register_namespace("", namespace)
    texto = ET.tostring(elemento, encoding="unicode")
    return ET.canonicalize(texto, strip_text=False).encode("utf-8")


def _tag_local(elemento):
    return elemento.tag.rsplit("}", 1)[-1]


def _namespace(elemento):
    return elemento.tag[1:].split("}", 1)[0] if elemento.tag.startswith("{") else ""


def _achar_por_id(raiz, id_):
    for el in raiz.iter():
        if el.get("Id") == id_:
            return el
    raise ErroAssinatura(f"elemento com Id='{id_}' não encontrado")


def _b64(dados):
    return base64.b64encode(dados).decode("ascii")


def _signed_info(id_, algoritmo, resumo_b64):
    alg = ALGORITMOS[algoritmo]
    return (f'<SignedInfo xmlns="{NS_DSIG}">'
            f'<CanonicalizationMethod Algorithm="{URI_C14N}"></CanonicalizationMethod>'
            f'<SignatureMethod Algorithm="{alg["assinatura"]}"></SignatureMethod>'
            f'<Reference URI="#{id_}"><Transforms>'
            f'<Transform Algorithm="{URI_ENVELOPED}"></Transform><Transform Algorithm="{URI_C14N}"></Transform></Transforms>'
            f'<DigestMethod Algorithm="{alg["resumo"]}"></DigestMethod><DigestValue>{resumo_b64}</DigestValue></Reference>'
            f'</SignedInfo>')


def assinar(xml, id_elemento, certificado, algoritmo="sha256"):
    """Devolve o XML com <Signature> dentro da raiz. `certificado` é um nfse.certificado.Certificado."""
    if algoritmo not in ALGORITMOS:
        raise ErroAssinatura(f"algoritmo desconhecido: {algoritmo!r}")
    alg = ALGORITMOS[algoritmo]
    raiz = ET.fromstring(xml)
    ns = _namespace(raiz)
    alvo = _achar_por_id(raiz, id_elemento)
    if any(_tag_local(f) == "Signature" for f in raiz):
        raise ErroAssinatura("o XML já tem uma assinatura")
    resumo = _b64(alg["hashlib"](_canonico(alvo, ns)).digest())
    signed_info = _signed_info(id_elemento, algoritmo, resumo)
    a_assinar = ET.canonicalize(signed_info, strip_text=False).encode("utf-8")
    valor = certificado.chave_privada.sign(a_assinar, padding.PKCS1v15(), alg["hash"]())
    der = certificado.certificado.public_bytes(serialization.Encoding.DER)
    assinatura = (f'<Signature xmlns="{NS_DSIG}">{signed_info}<SignatureValue>{_b64(valor)}</SignatureValue>'
                  f'<KeyInfo><X509Data><X509Certificate>{_b64(der)}</X509Certificate></X509Data></KeyInfo></Signature>')
    fim = xml.rstrip().rfind("</")
    if fim < 0:
        raise ErroAssinatura("XML sem tag de fechamento da raiz")
    return xml[:fim] + assinatura + xml[fim:]


def verificar(xml_assinado):
    """Refaz a conta de ponta a ponta (resumo + assinatura com a chave pública do próprio XML). Devolve (ok, motivo)."""
    try:
        raiz = ET.fromstring(xml_assinado)
        ns = _namespace(raiz)
        sig = next(f for f in raiz if _tag_local(f) == "Signature")
        si = next(f for f in sig if _tag_local(f) == "SignedInfo")
        ref = next(f for f in si if _tag_local(f) == "Reference")
        id_ = ref.get("URI", "")[1:]
        alvo = _achar_por_id(raiz, id_)
        metodo = next(f for f in si if _tag_local(f) == "SignatureMethod").get("Algorithm")
        algoritmo = next((k for k, v in ALGORITMOS.items() if v["assinatura"] == metodo), None)
        if algoritmo is None:
            return False, f"algoritmo de assinatura não suportado: {metodo}"
        alg = ALGORITMOS[algoritmo]
        esperado = next(f for f in ref if _tag_local(f) == "DigestValue").text.strip()
        calculado = _b64(alg["hashlib"](_canonico(alvo, ns)).digest())
        if esperado != calculado:
            return False, "o resumo (digest) não bate: o conteúdo mudou depois de assinar"
        valor = base64.b64decode(next(f for f in sig if _tag_local(f) == "SignatureValue").text)
        der = base64.b64decode(next(el for el in sig.iter() if _tag_local(el) == "X509Certificate").text)
        from cryptography import x509
        publica = x509.load_der_x509_certificate(der).public_key()
        publica.verify(valor, _canonico(si, NS_DSIG), padding.PKCS1v15(), alg["hash"]())
        return True, f"assinatura confere ({algoritmo})"
    except StopIteration:
        return False, "estrutura de assinatura incompleta"
    except Exception as erro:   # noqa: BLE001  qualquer falha de verificação vira "não confere", sem vazar detalhe
        return False, f"assinatura não confere ({erro.__class__.__name__})"
