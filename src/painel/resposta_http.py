"""Resposta da API para a tela: gzip e a assinatura que decide se "não mudou nada" (`__igual`)."""
import gzip
import hashlib
import json
import re

VOLATEIS_TELA = {"atualizado_em", "visto", "dias"}   # mudam sozinhos a cada volta: fora da comparação do "igual"
VOLATEIS_JUNTO = ("atualizado_em", "pcs")            # ... e estes vão junto com o {"__igual"} (cabeçalho em dia)

# Os campos que mudam sozinhos (VOLATEIS_TELA), em qualquer profundidade do JSON. Valor: texto, número, null ou booleano.
_RE_VOLATEIS = re.compile(r'"(?:' + "|".join(sorted(VOLATEIS_TELA)) + r')": (?:"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|null|true|false)')


def comprimir_se_vale(dados, aceita):
    """gzip só quando o navegador aceita e o corpo passa de 1 KB (auditoria 27/10/2026: /api/estado 1,8 MB -> 202 KB).
    -> (bytes, comprimido?)"""
    if len(dados) < 1024 or "gzip" not in (aceita or "").lower():
        return dados, False
    return gzip.compress(dados, compresslevel=4, mtime=0), True


def assinatura_do_texto(texto):
    """Hash do JSON já serializado, sem os campos que mudam sozinhos. Uma passada só (09/11/2026, fluidez): antes a tela
    percorria a estrutura inteira em Python e serializava de novo, uns 200 ms por resposta de 2 MB, mesmo sem novidade."""
    return hashlib.sha1(_RE_VOLATEIS.sub("", texto).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def assinatura_tela(corpo):
    """Hash do que a tela mostra, sem o que muda sozinho a cada volta (VOLATEIS_TELA). Velocidade 3, 21/10/2026."""
    return assinatura_do_texto(json.dumps(corpo, ensure_ascii=False, default=str))
