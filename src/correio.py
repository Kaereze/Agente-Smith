"""Caixa de correio do Painel: junta os espelhos dos 4 PCs (abas Correio_<PC>) com o lido/excluído da equipe.

Regras do usuário (08/10/2026):
- 1 linha por hóspede (o mesmo endereço), com o último e-mail e quantos são; abrir mostra a conversa toda.
- Caixa de Entrada: o que está sem resposta. Respondido (por QUALQUER caixa da rede, de qualquer PC) some.
- Urgência: sem resposta há mais de 7 dias, ou pedido de correção/cancelamento de NF (vai na hora).
- Itens Enviados: 72 h. Mais de 14 dias sem resposta: já saiu do espelho no PC dono.
- Lido / não lido vale pra equipe toda ("lido por Clara às 10:32"); não mexe no Outlook.
- Excluir: some na hora pra todos; o PC dono move pra Itens Excluídos do Outlook dele.
- Etapa 2 (09/10/2026): prazo por tipo (prazos.py), contado do 1º e-mail sem resposta da conversa; a NF do hóspede
  que saiu pra outro CPF/CNPJ põe os e-mails dele em Urgência (alertas: {endereço: texto}).
"""
import datetime

import espelho_emails as ee
import prazos

PRIORIDADE_CLASSES = ["corrigir", "complementar", "cobranca", "dados_tomador", "pedido_nf"]


def _data(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso)[:19])
    except ValueError:
        return None


def motivo_urgencia(classes, dias, alerta="", de="", nome=""):
    if alerta:
        return alerta
    if "ouvidoria" in f"{de} {nome}".lower():   # e-mail da Ouvidoria entra como urgente (usuário, 20/10/2026)
        return "E-mail da Ouvidoria"
    if "corrigir" in classes:
        return "Pedido de correção/cancelamento da NF"
    return f"{int(dias)} dias sem resposta" if dias > ee.URGENCIA_DIAS else ""


def lido_atual(e, ev):
    """Lido/não lido do Outlook (usuário, 11/10/2026). Um clique no Painel mais novo que a última leitura do
    espelho vale até o PC dono levar pro Outlook. PC na versão antiga (sem a coluna): o lido da equipe."""
    if e.get("lido_outlook") is None:
        return ev.get("lido", False)
    if ev.get("lido_mudou_em") and ev["lido_mudou_em"] >= e.get("atualizado", ""):
        return ev.get("lido", False)
    return bool(e["lido_outlook"])


def juntar(emails, eventos, agora, alertas=None):
    """emails: linhas de todas as Correio_<PC> (espelho_emails.ler_aba). eventos: espelho_emails.dobrar_eventos.
    alertas: {endereço: "CPF/CNPJ da NF ... diferente do pedido"} (vai pra Urgência).
    -> (entrada [e-mail], enviados [e-mail], respostas {endereço: último envio iso})"""
    alertas = alertas or {}
    respostas = {}
    for e in emails:
        if e["pasta"] == ee.RESPOSTA and e["quando"] > respostas.get(e["de"], ""):
            respostas[e["de"]] = e["quando"]
    entrada, enviados, vistos = [], [], set()
    for e in emails:
        ev = eventos.get(e["id"], {})
        if ev.get("excluido") or e["pasta"] == ee.RESPOSTA:
            continue
        repetido = (e["pasta"], e["caixa"], e["de"], e["assunto"], e["quando"])   # mesma caixa em 2 PCs
        if repetido in vistos:
            continue
        vistos.add(repetido)
        if e["pasta"] == ee.ENVIADO:
            enviados.append(e)
            continue
        # espelho literal (14/10/2026): respondido (por qualquer caixa da rede), solicitação do formulário e aviso do
        # Outlook ficam na lista, como no Outlook; só não contam como "esperando resposta" nem viram urgência
        respondido = respostas.get(e["de"], "") > e["quando"]
        especial = respondido or bool({"formulario", "aviso"} & set(e["classes"]))
        quando = _data(e["quando"])
        dias = (agora - quando).total_seconds() / 86400 if quando else 0
        motivo = "" if especial else motivo_urgencia(e["classes"], dias, alertas.get(e["de"], ""), e["de"], e.get("nome", ""))
        # marcado pela equipe (botão direito): vale o clique enquanto o PC dono não grava no Outlook; depois, a categoria
        marca = ev.get("urgencia") if ev.get("urgencia_em") and ev["urgencia_em"] >= e.get("atualizado", "") else \
            {"marcado_urgente": "urgente", "marcado_normal": "normal"}.get(next((c for c in e["classes"] if c.startswith("marcado_")), ""), "")
        if marca == "urgente":
            motivo = "Marcado como urgente" + (f" por {ev['urgencia_por']}" if ev.get("urgencia") == "urgente" and ev.get("urgencia_por") else "")
        elif marca == "normal":
            motivo = ""
        entrada.append({**e, "respondido": respondido, "pendente": not especial,
                        "lido": lido_atual(e, ev), "lido_por": ev.get("lido_por", ""),
                        "lido_em": ev.get("lido_em", ""), "dias": round(dias, 2),
                        "urgente": bool(motivo), "motivo_urgencia": motivo, "alerta_doc": alertas.get(e["de"], "")})
    entrada.sort(key=lambda e: e["quando"], reverse=True)
    enviados.sort(key=lambda e: e["quando"], reverse=True)
    return entrada, enviados, respostas


def conversas(entrada):
    """E-mails da entrada -> 1 conversa por hóspede (endereço), a mais recente primeiro."""
    grupos = {}
    for e in entrada:   # já vem do mais novo pro mais velho
        g = grupos.get(e["de"])
        if g is None:
            g = grupos[e["de"]] = {"de": e["de"], "nome": e["nome"] or e["de"], "ultimo": e, "ids": [], "hoteis": [],
                                   "pcs": [], "classes": [], "nao_lidos": 0, "urgente": False, "desde": e["quando"],
                                   "quartos": 0, "falta_nota": False}
        g["ids"].append(e["id"])
        g["desde"] = min(g["desde"], e["quando"])
        g["nao_lidos"] += 0 if e["lido"] else 1
        g["urgente"] = g["urgente"] or e["urgente"]
        g["quartos"] = max(g["quartos"], e.get("quartos") or 0)
        g["falta_nota"] = g["falta_nota"] or bool(e.get("falta_nota"))
        if not g["nome"] or g["nome"] == g["de"]:
            g["nome"] = e["nome"] or g["nome"]
        for campo, valor in (("hoteis", e["hotel"]), ("pcs", e["pc"])):
            if valor and valor not in g[campo]:
                g[campo].append(valor)
        for c in e["classes"]:
            if c not in g["classes"]:
                g["classes"].append(c)
    saida = list(grupos.values())
    for g in saida:
        g["classes"].sort(key=lambda c: PRIORIDADE_CLASSES.index(c) if c in PRIORIDADE_CLASSES else 99)
        g["total"] = len(g["ids"])
        g["prazo"] = prazos.vencimento(g["desde"], g["classes"])   # o relógio corre desde o 1º e-mail sem resposta
    return saida


def contagem(convs, entrada=None):
    """Números do menu. Caixa de entrada = igual ao Outlook: TODOS os e-mails da caixa (lidos e não lidos,
    respondidos, formulário, avisos). Urgência = conversas esperando resposta que viraram urgência."""
    if entrada is not None:
        return {"entrada_nao_lidos": sum(1 for e in entrada if not e["lido"]), "entrada": len(entrada),
                "urgencia": sum(1 for c in convs if c["urgente"]),
                "urgencia_nao_lidos": sum(c["nao_lidos"] for c in convs if c["urgente"])}
    return {"entrada_nao_lidos": sum(c["nao_lidos"] for c in convs if not c["urgente"]),
            "entrada": sum(1 for c in convs if not c["urgente"]),
            "urgencia": sum(1 for c in convs if c["urgente"]),
            "urgencia_nao_lidos": sum(c["nao_lidos"] for c in convs if c["urgente"])}


def novas_urgencias(convs, ja_avisadas):
    """Conversas que acabaram de entrar em Urgência (pro aviso do Windows): -> ([conversa], avisadas atualizado)."""
    agora_urgentes = {c["de"]: c for c in convs if c["urgente"]}
    novas = [c for de, c in agora_urgentes.items() if de not in ja_avisadas]
    return novas, set(agora_urgentes)
