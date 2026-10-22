"""Pedido que veio por ligação (usuário, 22/10/2026): os telefones não ligam no PC, então quem marca é o agente, no botão
"Ligação" da tela de escrever ou depois, no botão direito de um e-mail enviado. Cada marca é uma linha na aba Ligacoes
da Central (só se acrescenta; a última linha de cada chave vale). A chave é o id do envio do Painel (ENV-…) ou, para e-mail
que saiu direto do Outlook, o id dele no espelho. A marca nunca vai no e-mail do hóspede."""
import datetime
import socket

ABA = "Ligacoes"
CABECALHO = ["Quando", "Chave", "Ação", "Agente", "PC", "Hotel", "Caixa", "Para", "Assunto"]
MARCAR, DESMARCAR = "LIGACAO", "SEM_LIGACAO"
DIAS_GUARDADOS = 400   # a faxina apaga o que passou disso (o cartão mostra até o mês)


def evento(chave, acao, agente, hotel="", caixa="", para="", assunto="", pc=None, quando=None):
    return [(quando or datetime.datetime.now()).isoformat(timespec="seconds"), chave, acao, agente,
            pc or socket.gethostname(), hotel, caixa, para, assunto]


def chave_do_enviado(e):
    """Itens Enviados: o id do envio que o Painel gravou na marca invisível ("painel|ENV-…"), ou o id do e-mail."""
    via = str(e.get("via") or "")
    return via.split("|", 1)[1] if via.startswith("painel|ENV-") else str(e.get("id") or "")


def dobrar(linhas):
    """-> {chave: {"quando", "agente", "pc", "hotel", "caixa", "para", "assunto"}} só das chaves marcadas agora.
    "quando" e "agente" são os da primeira marca (desmarcar e marcar de novo não muda o dia da ligação)."""
    estado, primeira = {}, {}
    for l in linhas[1:]:
        l = [str(v) for v in l] + [""] * (len(CABECALHO) - len(l))
        quando, chave, acao, agente, pc, hotel, caixa, para, assunto = l[:9]
        if not chave or acao not in (MARCAR, DESMARCAR):
            continue
        if acao == MARCAR:
            primeira.setdefault(chave, {"quando": quando, "agente": agente, "pc": pc, "hotel": hotel, "caixa": caixa,
                                        "para": para, "assunto": assunto})
        estado[chave] = acao
    return {c: primeira[c] for c, a in estado.items() if a == MARCAR and c in primeira}


def resumo(marcadas, envios_hoje=0, hoje=None):
    """Cartão da Visão geral: hoje, 7 dias e o mês, e os últimos 7 dias por hotel e por agente."""
    hoje = hoje or datetime.date.today()
    h, ini7, ini_mes = hoje.isoformat(), (hoje - datetime.timedelta(days=6)).isoformat(), hoje.replace(day=1).isoformat()
    dia, semana, mes, por_hotel, por_agente = 0, 0, 0, {}, {}
    for m in marcadas.values():
        d = m["quando"][:10]
        if d > h:
            continue
        dia += d == h
        mes += d >= ini_mes
        if d >= ini7:
            semana += 1
            hotel = m["hotel"] or "Sem hotel"
            por_hotel[hotel] = por_hotel.get(hotel, 0) + 1
            por_agente[m["agente"] or "Sem agente"] = por_agente.get(m["agente"] or "Sem agente", 0) + 1
    ordem = lambda d: sorted(d.items(), key=lambda x: (-x[1], x[0]))   # noqa: E731
    return {"hoje": dia, "semana": semana, "mes": mes, "envios_hoje": envios_hoje,
            "por_hotel": ordem(por_hotel), "por_agente": ordem(por_agente)}


def envios_falhos_a_desmarcar(marcadas, fila, pc):
    """Envio do Painel marcado como ligação que falhou: este PC (o que marcou) tira a marca, senão o reenvio conta 2 vezes."""
    return [c for c, m in marcadas.items()
            if c.startswith("ENV-") and m["pc"] == pc and (fila.get(c) or {}).get("resultado") == "FALHOU"]
