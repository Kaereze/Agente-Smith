"""Pedido do titular (LGPD, 08/11/2026): onde os dados de UMA pessoa estão neste PC e como tirar do que dá para tirar daqui.

Quem pediu ver ou apagar os dados informa o CPF/CNPJ, o e-mail ou o nome. A ferramenta (ferramentas/pedido_titular.py) usa isto aqui:

- `localizar(termo)`: conta onde a pessoa aparece em cada dado pessoal do catálogo (src/sistema/armazem.py). Só números; o conteúdo nunca é mostrado.
- `apagar_do_indice(termo)`: tira os e-mails dela do índice de pesquisa deste PC.
- `apagar_arquivo(arquivo)`: apaga um cache inteiro que a contém (só os que o catálogo marca como reconstruíveis); o Painel refaz depois.

O que isto NÃO faz, de propósito: apagar do Outlook, da planilha do hotel ou da Planilha Central (é lá que o dado nasce: o hotel apaga a
linha e a Central acompanha), nem apagar NF emitida (obrigação fiscal, guarda de 5 anos). Se a fonte continuar com o dado, o Painel o lê de novo.
"""
import re

from sistema import armazem
from emails import indice_emails


def termos(texto):
    """Formas de procurar a mesma pessoa: CPF/CNPJ só com números e formatado, e-mail em minúsculas, ou o nome."""
    t = str(texto or "").strip()
    if not t:
        return []
    digitos = re.sub(r"\D", "", t)
    if "@" not in t and len(digitos) in (11, 14) and not re.search(r"[A-Za-zÀ-ÿ]", t):
        if len(digitos) == 11:
            return [digitos, f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"]
        return [digitos, f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"]
    return [t.lower()]


def _no_indice(indice, ts):
    achados = {}
    for t in ts:
        for e in indice.buscar(t, limite=100000):
            achados[e["id"]] = e
    return achados


def localizar(termo, indice=None):
    """-> {arquivo: quantidade}. SQLite: e-mails no índice. JSON e cache: quantas vezes aparece no arquivo. Nada do conteúdo sai daqui."""
    ts = termos(termo)
    if not ts:
        return {}
    res = {}
    indice = indice or indice_emails.Indice()
    n = len(_no_indice(indice, ts))
    if n:
        res["indice_emails.sqlite"] = n
    for d in armazem.pessoais():
        if d.formato not in ("json", "cache") or d.arquivo in ("indice_emails.sqlite",) or "AAAA" in d.arquivo:
            continue
        p = armazem.caminho(d.arquivo)
        if not p.exists() or p.stat().st_size > 200_000_000:
            continue
        texto = p.read_bytes().decode("utf-8", errors="ignore").lower()
        c = sum(texto.count(t.lower()) for t in ts)
        if c:
            res[d.arquivo] = c
    return res


def apagar_do_indice(termo, indice=None):
    """Tira do índice de pesquisa deste PC os e-mails em que a pessoa aparece. -> quantos saíram."""
    ts = termos(termo)
    indice = indice or indice_emails.Indice()
    ids = list(_no_indice(indice, ts)) if ts else []
    if ids:
        indice.tirar(ids)
    return len(ids)


def apagar_arquivo(arquivo):
    """Apaga um cache inteiro. Só os que o catálogo diz que se reconstroem e que têm dado pessoal. -> True se apagou."""
    d = armazem.DADOS.get(arquivo)
    if not d or not d.pessoal or not d.refaz or d.formato not in ("json", "cache"):
        raise ValueError(f"'{arquivo}' não pode ser apagado por aqui (não é cache reconstruível com dado pessoal)")
    p = armazem.caminho(arquivo)
    if not p.exists():
        return False
    p.unlink()
    return True
