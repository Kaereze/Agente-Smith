"""Registro de quem viu o dado do hóspede (LGPD, 08/11/2026).

Cada vez que alguém abre o texto de um e-mail, um anexo ou a ficha de um pedido, o Painel anota: quando, quem (operador), de qual PC, o tipo
e uma referência curta do item. **Nunca** grava nome, CPF/CNPJ, e-mail ou texto do hóspede: a referência é um pedaço do código do item
(SHA-1), que só serve para o Painel achar o mesmo item de novo. Fica só neste PC, em `estado/acessos/AAAA-MM.jsonl`, por 12 meses.
Se o registro falhar, a tela segue normalmente (o registro nunca derruba a leitura).
"""
import collections
import datetime
import hashlib
import json
import threading

import armazem
from log_util import configurar_logging

logger = configurar_logging("app")
TIPOS = ("email", "anexo", "ficha")
GUARDA_MESES = 12
_trava = threading.Lock()


def referencia(item):
    """Pedaço do código do item (nunca o código inteiro, nunca o conteúdo)."""
    return hashlib.sha1(str(item or "").encode("utf-8")).hexdigest()[:10]


def registrar(agente, pc, tipo, item="", hotel="", agora=None):
    """Anota um acesso. -> True se gravou (False: tipo desconhecido ou erro, que só vai para o log técnico)."""
    if tipo not in TIPOS:
        return False
    agora = agora or datetime.datetime.now()
    linha = {"quando": agora.isoformat(timespec="seconds"), "agente": str(agente or "")[:40], "pc": str(pc or "")[:40], "tipo": tipo,
             "ref": referencia(item), "hotel": str(hotel or "")[:40]}
    try:
        pasta = armazem.caminho("acessos")
        with _trava:
            pasta.mkdir(parents=True, exist_ok=True)
            with open(pasta / f"{agora:%Y-%m}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        logger.debug(f"registro de acesso não gravado: {e}")
        return False


def ler(mes=None):
    """Linhas de um mês (AAAA-MM; padrão: o atual)."""
    mes = mes or f"{datetime.date.today():%Y-%m}"
    arq = armazem.caminho("acessos") / f"{mes}.jsonl"
    if not arq.exists():
        return []
    linhas = []
    for l in arq.read_text(encoding="utf-8").splitlines():
        try:
            linhas.append(json.loads(l))
        except ValueError:
            continue   # linha cortada por queda de energia: ignora
    return linhas


def resumo(mes=None):
    """Quantos acessos cada operador fez no mês, por tipo: {"João": {"email": 12, "anexo": 1, "ficha": 3}, ...}"""
    por = collections.defaultdict(lambda: collections.Counter())
    for l in ler(mes):
        por[l.get("agente", "?")][l.get("tipo", "?")] += 1
    return {a: dict(c) for a, c in sorted(por.items())}


def limpar(hoje=None, meses=GUARDA_MESES):
    """Apaga os arquivos mais velhos que `meses`. -> quantos arquivos saíram."""
    hoje = hoje or datetime.date.today()
    limite = (hoje.year * 12 + hoje.month) - meses
    pasta = armazem.caminho("acessos")
    if not pasta.exists():
        return 0
    n = 0
    for f in pasta.glob("*.jsonl"):
        try:
            ano, mes = (int(x) for x in f.stem.split("-"))
        except ValueError:
            continue
        if ano * 12 + mes < limite:
            f.unlink(missing_ok=True)
            n += 1
    return n
