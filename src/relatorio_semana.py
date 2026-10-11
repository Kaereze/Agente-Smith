"""Relatório do dia e da semana na Gerência (usuário, 11/10/2026): os números que o Mail Analytics já grava na planilha dele
(e-mails recebidos e enviados, ligações, substituições/cancelamentos e NFs emitidas, por operador, dia e hotel)
mais os pedidos de formulário do Painel. Compara com a semana anterior e monta um resumo pronto pra mandar.

SÓ LÊ a planilha do Mail Analytics (o código dele não é mexido — regra do usuário). 1 leitura em lote das 4 abas,
guardada 30 min (cota do Google).
"""
import datetime
import time

PLANILHA_MAIL_ANALYTICS = "1e78L9EJeYzW_jWOZF5jqKPKu9vmKs1ZBstV_2FLZ_rY"
ABAS = {"João": "Agente_Joao", "Clara": "Agente_Clara", "Cristian": "Agente_Cristian", "Bernardo": "Agente_Bernardo"}
CAMPOS = [("recebidos", "Emails Recebidos"), ("enviados", "Emails Enviados"), ("ligacoes", "Ligações"),
          ("subst_canc", "Substituições/Cancelamentos"), ("nfs", "NFs Emitidas")]
CACHE_SEGUNDOS = 30 * 60
_CACHE = {"em": -1e9, "dados": None}


def _num(v):
    try:
        return int(float(str(v).replace(",", ".").strip() or 0))
    except ValueError:
        return 0


def _dia(texto):
    try:
        return datetime.datetime.strptime(str(texto).strip()[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def ler(backend, planilha=PLANILHA_MAIL_ANALYTICS, forcar=False):
    """-> {agente: [{"dia", "hotel", recebidos, enviados, ligacoes, subst_canc, nfs}]} (guardado 30 min)."""
    if not forcar and _CACHE["dados"] is not None and time.monotonic() - _CACHE["em"] < CACHE_SEGUNDOS:
        return _CACHE["dados"]
    lidas, _ = backend.ler_abas(planilha, list(ABAS.values()))
    saida = {}
    for agente, aba in ABAS.items():
        linhas = lidas.get(aba) or []
        if not linhas:
            continue
        cab = [str(c).strip() for c in linhas[0]]
        idx = {k: cab.index(nome) for k, nome in CAMPOS if nome in cab}
        regs = []
        for l in linhas[1:]:
            if not l or len(l) < 2:
                continue
            dia = _dia(l[0])
            if not dia:
                continue
            reg = {"dia": dia, "hotel": str(l[1]).strip()}
            for k, i in idx.items():
                reg[k] = _num(l[i]) if i < len(l) else 0
            regs.append(reg)
        saida[agente] = regs
    _CACHE.update(em=time.monotonic(), dados=saida)
    return saida


def semana(referencia, deslocamento=0):
    """Segunda a domingo da semana de `referencia` (deslocamento 1 = a semana anterior)."""
    ini = referencia - datetime.timedelta(days=referencia.weekday() + 7 * deslocamento)
    return ini, ini + datetime.timedelta(days=6)


def _somar(regs, ini, fim):
    total = {k: 0 for k, _ in CAMPOS}
    dias = set()
    for r in regs:
        if ini <= r["dia"] <= fim:
            dias.add(r["dia"])
            for k, _ in CAMPOS:
                total[k] += r.get(k, 0)
    total["dias"] = len(dias)
    return total


AGENTES_FIM_DE_SEMANA = ("João", "Cristian")


def juntar_fontes(ma, painel, tipo):
    """Mail Analytics + contagem do fim de semana do Painel, sem contar em dobro (usuário, 11/10/2026).
    O Mail Analytics de João e Cristian grava sexta+sábado+domingo numa linha só (a do domingo), na segunda de manhã.
    - Semana: se a linha do domingo já existe, vale a dela; se não, entra a contagem do Painel daqueles dias.
    - Dia: sexta, sábado e domingo vêm da contagem do Painel (separada por dia); a linha somada do domingo sai.
    -> ({agente: [registros]}, [agentes com dias contados pelo Painel])"""
    saida, usou = {}, []
    for agente in set(ma) | set(painel or {}):
        regs = list(ma.get(agente, []))
        p = (painel or {}).get(agente, [])
        if p and agente in AGENTES_FIM_DE_SEMANA:
            dias_ma = {r["dia"] for r in regs}
            blocos = {}
            for r in p:
                blocos.setdefault(r["dia"] + datetime.timedelta(days=6 - r["dia"].weekday()), []).append(r)
            for domingo, rp in blocos.items():
                if tipo == "dia":
                    regs = [r for r in regs if r["dia"] != domingo] + rp
                elif domingo not in dias_ma:
                    regs += rp
                else:
                    continue
                if agente not in usou:
                    usou.append(agente)
        saida[agente] = regs
    return saida, sorted(usou)


def periodo(hoje, tipo="semana", deslocamento=0):
    """-> (ini, fim, ini_anterior, fim_anterior). Dia: o dia (hoje - deslocamento) contra o dia anterior."""
    if tipo == "dia":
        d = hoje - datetime.timedelta(days=deslocamento)
        return d, d, d - datetime.timedelta(days=1), d - datetime.timedelta(days=1)
    ini, fim = semana(hoje, deslocamento)
    return (ini, fim) + semana(hoje, deslocamento + 1)


def montar(dados, hoje, deslocamento=0, pedidos=None, tipo="semana", painel=None):
    """dados: ler() (Mail Analytics). pedidos: [(data iso, agente)] dos formulários do Painel. tipo: "semana" | "dia".
    painel: contagem do fim de semana do Painel (contagem_painel.ler_abas). -> dict pro Painel."""
    dados, contado_painel = juntar_fontes(dados, painel, tipo)
    if tipo == "dia" and deslocamento < 0:   # "auto": o último dia que o Mail Analytics já gravou
        ultimo = max((r["dia"] for regs in dados.values() for r in regs if r["dia"] <= hoje), default=hoje)
        deslocamento = (hoje - ultimo).days
    ini, fim, ini_ant, fim_ant = periodo(hoje, tipo, deslocamento)
    fim_real = min(fim, hoje)
    por_agente, anterior = {}, {}
    for agente, regs in dados.items():
        por_agente[agente] = _somar(regs, ini, fim)
        anterior[agente] = _somar(regs, ini_ant, fim_ant)
    for agente, d in por_agente.items():
        d["pedidos"] = sum(1 for q, a in (pedidos or []) if a == agente and ini.isoformat() <= q <= fim.isoformat())
        anterior[agente]["pedidos"] = sum(1 for q, a in (pedidos or []) if a == agente and ini_ant.isoformat() <= q <= fim_ant.isoformat())
    chaves = [k for k, _ in CAMPOS] + ["pedidos"]
    total = {k: sum(d.get(k, 0) for d in por_agente.values()) for k in chaves}
    total_ant = {k: sum(d.get(k, 0) for d in anterior.values()) for k in chaves}
    hoteis = {}
    for agente, regs in dados.items():
        for r in regs:
            if ini <= r["dia"] <= fim:
                h = hoteis.setdefault(r["hotel"], {"hotel": r["hotel"], "agente": agente, "recebidos": 0, "nfs": 0, "subst_canc": 0})
                for k in ("recebidos", "nfs", "subst_canc"):
                    h[k] += r.get(k, 0)
    top = sorted(hoteis.values(), key=lambda h: (h["recebidos"], h["nfs"]), reverse=True)[:8]
    ultimo_dia = {a: max((r["dia"] for r in regs), default=None) for a, regs in dados.items()}
    return {"ini": ini.isoformat(), "fim": fim.isoformat(), "ate": fim_real.isoformat(), "deslocamento": deslocamento,
            "por_agente": por_agente, "anterior": anterior, "total": total, "total_anterior": total_ant,
            "hoteis": top, "ultimo_dia": {a: d.isoformat() if d else "" for a, d in ultimo_dia.items()},
            "tipo": tipo, "contado_painel": [a for a in contado_painel if por_agente.get(a, {}).get("dias")],
            "texto": resumo_texto(ini, fim_real, por_agente, total, total_ant, top, tipo)}


def _var(agora, antes, tipo="semana"):
    if not antes:
        return ""
    v = round(100 * (agora - antes) / antes)
    contra = "dia anterior" if tipo == "dia" else "semana anterior"
    return f" ({'+' if v > 0 else ''}{v}% vs {contra})" if v else f" (igual ao {contra})" if tipo == "dia" else f" (igual à {contra})"


def resumo_texto(ini, fim, por_agente, total, total_ant, top, tipo="semana"):
    """Texto pronto pra colar no WhatsApp/e-mail do gerente."""
    titulo = f"Relatório do dia — {ini:%d/%m/%Y}" if tipo == "dia" else f"Relatório da semana — {ini:%d/%m} a {fim:%d/%m}"
    _v = lambda a, b: _var(a, b, tipo)
    linhas = [titulo, "",
              f"• Pedidos de NF (formulário): {total['pedidos']}{_v(total['pedidos'], total_ant['pedidos'])}",
              f"• E-mails recebidos: {total['recebidos']}{_v(total['recebidos'], total_ant['recebidos'])}",
              f"• E-mails enviados: {total['enviados']}{_v(total['enviados'], total_ant['enviados'])}",
              f"• NFs emitidas: {total['nfs']}{_v(total['nfs'], total_ant['nfs'])}",
              f"• Substituições/cancelamentos: {total['subst_canc']}",
              f"• Ligações: {total['ligacoes']}", "", "Por operador:"]
    for a, d in sorted(por_agente.items(), key=lambda x: -x[1]["nfs"]):
        linhas.append(f"• {a}: {d['nfs']} NFs · {d['recebidos']} e-mails recebidos · {d['enviados']} enviados · "
                      f"{d['pedidos']} pedidos · {d['subst_canc']} subst./canc.")
    if top:
        linhas += ["", "Hotéis com mais movimento:"]
        linhas += [f"• {h['hotel']} ({h['agente']}): {h['recebidos']} e-mails · {h['nfs']} NFs" for h in top[:5]]
    return "\n".join(linhas)
