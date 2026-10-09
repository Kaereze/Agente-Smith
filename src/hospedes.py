"""Hóspede único e pedido repetido — Etapa 2 (usuário, 09/10/2026).

Hóspede único: dois pedidos são do mesmo hóspede quando têm o mesmo e-mail OU o mesmo CPF/CNPJ. Trava contra
juntar gente diferente: CNPJ de empresa usado por muitos funcionários (mais de MAX_EMAILS_POR_CNPJ e-mails) e
e-mail de agência/empresa com muita gente (mais de MAX_DOCS_POR_EMAIL documentos) não ligam ninguém.
Medido nos 14,5 mil pedidos reais: 57 documentos aparecem com 5+ e-mails (empresas com grupos).

Pedido repetido ("junta e avisa"): mesmo hotel, mesmos CPF/CNPJ e mesma estadia (check-in/out) em outro
formulário. Vira 1 só: o principal é o que andou mais (NF > com alguém > tratativa > na fila), empate = o primeiro
enviado. Os outros ficam ligados a ele (repetido_de) e não contam de novo. Nos dados reais: 466 grupos (~3%),
metade reenviada no mesmo dia (clique duplo), a outra metade dias depois (o hóspede cobrando).
Só lê: nada é gravado na Central nem nas planilhas dos hotéis.
"""
import collections
import datetime
import re
import types

import prazos
from controle_nf import provas_da_solicitacao

MAX_EMAILS_POR_CPF = 3
MAX_EMAILS_POR_CNPJ = 2
MAX_DOCS_POR_EMAIL = 6
MAX_OUTROS = 8
ORDEM_SITUACAO = {"concluida": 0, "nf_parcial": 1, "em_tratamento": 2, "tratativa": 3, "na_fila": 4,
                  "aguardando_envio": 5}
SEM_PRAZO = ("tratativa",)   # esperando o hóspede responder: o relógio para

_CACHE_PROVAS = {}


def provas(s):
    chave = (s["chave"], s.get("linha"))
    if chave not in _CACHE_PROVAS:
        if len(_CACHE_PROVAS) > 50000:
            _CACHE_PROVAS.clear()
        _CACHE_PROVAS[chave] = provas_da_solicitacao(types.SimpleNamespace(campos=s.get("campos", [])))
    return _CACHE_PROVAS[chave]


def enderecos(s):
    return {str(x).strip().lower() for x in [s.get("email", "")] + list(s.get("emails", [])) if "@" in str(x)}


def inicio_do_pedido(s):
    """Data do formulário + hora do carimbo -> datetime | None."""
    try:
        dia = datetime.date.fromisoformat(str(s.get("data", ""))[:10])
    except ValueError:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", str(s.get("carimbo", "")))
    h, mi, se = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else (0, 0, 0)
    return datetime.datetime(dia.year, dia.month, dia.day, min(h, 23), min(mi, 59), min(se, 59))


class _Uniao:
    def __init__(self):
        self.pai = {}

    def achar(self, x):
        self.pai.setdefault(x, x)
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def unir(self, a, b):
        ra, rb = self.achar(a), self.achar(b)
        if ra != rb:
            self.pai[max(ra, rb)] = min(ra, rb)


def grupos(solicitacoes):
    """-> {chave do pedido: id do hóspede}"""
    docs_do_email, emails_do_doc = collections.defaultdict(set), collections.defaultdict(set)
    for s in solicitacoes:
        for e in enderecos(s):
            for d in provas(s)["documentos"]:
                docs_do_email[e].add(d)
                emails_do_doc[d].add(e)

    def liga(no):
        if no.startswith("e:"):
            return len(docs_do_email.get(no[2:], ())) <= MAX_DOCS_POR_EMAIL
        limite = MAX_EMAILS_POR_CPF if len(no) == 13 else MAX_EMAILS_POR_CNPJ   # "d:" + 11 dígitos = CPF
        return len(emails_do_doc.get(no[2:], ())) <= limite

    u = _Uniao()
    saida = {}
    for s in solicitacoes:
        nos = [n for n in [f"e:{e}" for e in sorted(enderecos(s))] + [f"d:{d}" for d in provas(s)["documentos"]] if liga(n)]
        proprio = "p:" + s["chave"]
        for n in nos:
            u.unir(proprio, n)
        saida[s["chave"]] = proprio
    return {k: u.achar(v) for k, v in saida.items()}


def _marca_estadia(s):
    """Mesmo hotel + mesmos CPF/CNPJ + mesma estadia + mesmo valor pedido. O valor separa as partes de uma nota
    dividida (a Andiara mandou 2 formulários de propósito: R$ 270 e R$ 280 — não é repetido)."""
    p = provas(s)
    if not p["documentos"] or not p["datas"]:
        return None
    valores = tuple(sorted(re.sub(r"\D", "", str(v)) for k, v in s.get("campos", []) if "valor" in str(k).lower()))
    return (s.get("aba"), tuple(p["documentos"]), tuple(p["datas"]), valores)


def _resumo(s):
    return {"chave": s["chave"], "data": s.get("data", ""), "carimbo": s.get("carimbo", ""), "hotel": s.get("hotel", ""),
            "nome": s.get("nome", ""), "email": s.get("email", ""), "situacao": s.get("situacao", ""),
            "nfs": list(s.get("nfs", []))}


def marcar(fila, agora=None):
    """Fila do Painel (app_dados.montar_fila) -> a mesma lista, cada pedido com:
    hospede (id), outros_pedidos [resumo], repetido_de (chave) | repetidos [resumo], prazo {vence, horas, ...} | None."""
    agora = agora or datetime.datetime.now()
    hosp = grupos(fila)
    por_hospede = collections.defaultdict(list)
    for s in fila:
        s["hospede"] = hosp[s["chave"]]
        por_hospede[s["hospede"]].append(s)
        s["repetido_de"], s["repetidos"] = "", []
    # repetidos: mesmo hotel + mesmos documentos + mesma estadia
    iguais = collections.defaultdict(list)
    for s in fila:
        marca = _marca_estadia(s)
        if marca:
            iguais[marca].append(s)
    for lista in iguais.values():
        if len(lista) < 2:
            continue
        principal = min(lista, key=lambda s: (ORDEM_SITUACAO.get(s.get("situacao"), 9), s.get("data", ""),
                                              str(inicio_do_pedido(s) or "")))
        for s in lista:
            if s is not principal:
                s["repetido_de"] = principal["chave"]
                principal["repetidos"].append(_resumo(s))
    for s in fila:
        ja = {s["chave"]} | {r["chave"] for r in s["repetidos"]} | ({s["repetido_de"]} if s["repetido_de"] else set())
        outros = [x for x in por_hospede[s["hospede"]] if x["chave"] not in ja and not x["repetido_de"]]
        outros.sort(key=lambda x: (x.get("data", ""), x.get("carimbo", "")), reverse=True)
        s["outros_pedidos"] = [_resumo(x) for x in outros[:MAX_OUTROS]]
        s["outros_total"] = len(outros)
        resolvido = s.get("situacao") == "concluida" and not s.get("envio_pendente")
        inicio = min([inicio_do_pedido(s)] + [inicio_do_pedido(r) for r in s["repetidos"]],
                     key=lambda d: d or datetime.datetime.max)
        s["prazo"] = None if resolvido or s.get("situacao") in SEM_PRAZO or not inicio else \
            prazos.vencimento(inicio, tipo_prazo="pedido")
    return fila
