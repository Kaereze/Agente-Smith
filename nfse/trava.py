"""Trava de ambiente: este código só pode falar com a PRODUÇÃO RESTRITA (teste) da NFS-e Nacional.

Três travas, todas barram com erro claro:
1. Endereço: só https e só os dois hosts de produção restrita (HOSTS_PERMITIDOS). Porta padrão, sem usuário na URL.
2. DPS e evento: o XML só sai se tpAmb = 2 (homologação / produção restrita).
3. Resposta: se o governo disser que o ambiente é outro (tipoAmbiente diferente de 2), o programa para.

Para liberar a produção de verdade no futuro será preciso mudar ESTE arquivo de propósito, com decisão do João
(registrar em Decisões). Não existe parâmetro, variável de ambiente nem opção de linha de comando que faça isso.
"""
import re
from urllib.parse import urlsplit

HOSTS_PERMITIDOS = frozenset({
    "sefin.producaorestrita.nfse.gov.br",
    "adn.producaorestrita.nfse.gov.br",
})
TP_AMB_TESTE = 2          # 1 = produção, 2 = homologação (produção restrita), conforme o Swagger oficial


class AmbienteProibido(Exception):
    """Algo tentou sair do ambiente de teste."""


def validar_url(url):
    """Aceita só https://<host de produção restrita>/... . Devolve a própria URL se estiver tudo certo."""
    partes = urlsplit(url)
    if partes.scheme != "https":
        raise AmbienteProibido(f"só https é permitido (veio '{partes.scheme}')")
    if partes.username or partes.password:
        raise AmbienteProibido("usuário/senha dentro da URL não é permitido")
    if partes.port not in (None, 443):
        raise AmbienteProibido(f"porta {partes.port} não é permitida")
    host = (partes.hostname or "").lower()
    if host not in HOSTS_PERMITIDOS:
        raise AmbienteProibido(f"endereço '{host}' fora da produção restrita; permitidos: {sorted(HOSTS_PERMITIDOS)}")
    return url


def tp_amb_do_xml(xml):
    """Lê o <tpAmb> do XML (DPS ou pedido de evento). None se não achar."""
    achou = re.search(r"<tpAmb>\s*(\d)\s*</tpAmb>", xml)
    return int(achou.group(1)) if achou else None


def validar_xml_de_teste(xml):
    """Barra DPS/evento que não seja de teste (tpAmb diferente de 2 ou ausente)."""
    tp = tp_amb_do_xml(xml)
    if tp != TP_AMB_TESTE:
        raise AmbienteProibido(f"tpAmb do XML é {tp!r}; só {TP_AMB_TESTE} (produção restrita) pode ser enviado")
    return xml


def validar_resposta(resposta_json):
    """Se a resposta do governo trouxer tipoAmbiente, ele tem de ser 2. Sem o campo, não há o que conferir."""
    if isinstance(resposta_json, dict) and "tipoAmbiente" in resposta_json:
        if resposta_json["tipoAmbiente"] != TP_AMB_TESTE:
            raise AmbienteProibido(f"o governo respondeu tipoAmbiente={resposta_json['tipoAmbiente']!r} (esperado {TP_AMB_TESTE}); "
                                   "parando por segurança")
    return resposta_json
