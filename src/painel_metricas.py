"""Números das telas Visão geral e Hotéis, juntando a Central (solicitações) e o Mail Analytics.

Funções puras: recebem listas já lidas e devolvem dicts prontos pro JSON.
"""
import datetime

import app_dados as dados
from fiscal_intelligence import METRICAS

PENDENTES = {dados.AGUARDANDO_ENVIO, dados.NA_FILA, dados.EM_TRATAMENTO, dados.EM_TRATATIVA, dados.NF_PARCIAL}
FAIXAS_IDADE = [("0–2 dias", 0, 2), ("3–7 dias", 3, 7), ("8–15 dias", 8, 15), ("16–30 dias", 16, 30), ("+30 dias", 31, 10 ** 6)]


def _dia(iso):
    return datetime.date.fromisoformat(iso) if iso else None


def _no_periodo(d, ini, fim):
    return d is not None and ini <= d <= fim


def _somar(regs):
    return {m: sum(r[m] for r in regs) for m in METRICAS}


def _idade(sol, hoje):
    d = _dia(sol["data"])
    return (hoje - d).days if d else 0


def pendentes_por_idade(fila, hoje, hotel=None):
    pend = [s for s in fila if s["situacao"] in PENDENTES and (hotel is None or s["hotel"] == hotel)]
    return [{"faixa": nome, "n": sum(1 for s in pend if lo <= _idade(s, hoje) <= hi)} for nome, lo, hi in FAIXAS_IDADE]


def serie_diaria(metricas, fila, ini, fim, fins_de_semana, hotel=None):
    regs = [m for m in metricas if hotel is None or m["hotel"] == hotel]
    sols = [s for s in fila if hotel is None or s["hotel"] == hotel]
    # O Mail Analytics grava o dia anterior: depois do último dia com dado, None (não é zero)
    ultimo_mail = max((m["data"] for m in metricas), default=None)
    serie, d = [], ini
    while d <= fim:
        do_dia = [m for m in regs if m["data"] == d]
        notas = sorted({f"{op}: {txt}" for (op, dom), txt in fins_de_semana.items() if dom == d
                        and (hotel is None or any(m["operador"] == op for m in do_dia))})
        mail = _somar(do_dia) if ultimo_mail and d <= ultimo_mail else {m: None for m in METRICAS}
        serie.append({"data": d.isoformat(), **mail,
                      "solicitacoes": sum(1 for s in sols if _dia(s["data"]) == d),
                      "fim_de_semana": notas})
        d += datetime.timedelta(days=1)
    return serie


def visao_geral(metricas, fila, ini, fim, hoje, fins_de_semana):
    regs = [m for m in metricas if _no_periodo(m["data"], ini, fim)]
    sols = [s for s in fila if _no_periodo(_dia(s["data"]), ini, fim)]
    concluidas = sum(1 for s in sols if s["situacao"] == dados.CONCLUIDA)
    pendentes_agora = [s for s in fila if s["situacao"] in PENDENTES]
    por_hotel = {}
    for s in pendentes_agora:
        por_hotel[s["hotel"]] = por_hotel.get(s["hotel"], 0) + 1
    return {
        "kpis": {**_somar(regs), "solicitacoes": len(sols), "concluidas": concluidas,
                 "taxa_atendimento": round(100 * concluidas / len(sols)) if sols else None,
                 "pendentes_agora": len(pendentes_agora),
                 "pendentes_7d": sum(1 for s in pendentes_agora if _idade(s, hoje) > 7)},
        "serie": serie_diaria(metricas, fila, ini, fim, fins_de_semana),
        "idade": pendentes_por_idade(fila, hoje),
        "top_pendentes": sorted(({"hotel": h, "n": n} for h, n in por_hotel.items()), key=lambda x: -x["n"])[:8],
    }


def tabela_hoteis(metricas, fila, ini, fim, hoje, cadastro):
    linhas = {}

    def linha(hotel):
        if hotel not in linhas:
            linhas[hotel] = {"hotel": hotel, "agente": cadastro.dados(hotel).get("agente", ""),
                             "operadores": set(), **{m: 0 for m in METRICAS},
                             "solicitacoes": 0, "concluidas": 0, "pendentes": 0, "mais_antigo": None}
        return linhas[hotel]

    for nome in cadastro.nomes():
        linha(nome)
    for m in metricas:
        if _no_periodo(m["data"], ini, fim):
            l = linha(m["hotel"])
            l["operadores"].add(m["operador"])
            for k in METRICAS:
                l[k] += m[k]
    for s in fila:
        l = linha(s["hotel"])
        if _no_periodo(_dia(s["data"]), ini, fim):
            l["solicitacoes"] += 1
            l["concluidas"] += s["situacao"] == dados.CONCLUIDA
        if s["situacao"] in PENDENTES:
            l["pendentes"] += 1
            idade = _idade(s, hoje)
            l["mais_antigo"] = max(l["mais_antigo"] or 0, idade)
    saida = []
    for l in linhas.values():
        l["operadores"] = sorted(l["operadores"])
        l["taxa_cancelamento"] = round(100 * l["cancelamentos"] / l["nfs"]) if l["nfs"] else None
        l["taxa_atendimento"] = round(100 * l["concluidas"] / l["solicitacoes"]) if l["solicitacoes"] else None
        saida.append(l)
    return sorted(saida, key=lambda l: (-l["pendentes"], l["hotel"]))


def ficha_hotel(hotel, metricas, fila, ini, fim, hoje, fins_de_semana, cadastro):
    regs = [m for m in metricas if m["hotel"] == hotel and _no_periodo(m["data"], ini, fim)]
    pend = sorted((s for s in fila if s["hotel"] == hotel and s["situacao"] in PENDENTES), key=lambda s: s["data"])
    return {"hotel": hotel, **cadastro.dados(hotel), "totais": _somar(regs),
            "serie": serie_diaria(metricas, fila, ini, fim, fins_de_semana, hotel),
            "idade": pendentes_por_idade(fila, hoje, hotel),
            "pendentes": [{"chave": s["chave"], "nome": s["nome"], "data": s["data"], "situacao": s["situacao"],
                           "dono": s["dono"], "idade": _idade(s, hoje)} for s in pend[:200]]}
