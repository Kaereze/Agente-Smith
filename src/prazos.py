"""Prazo de resposta (SLA) por tipo de pedido — Etapa 2 (usuário, 09/10/2026).

- Correção / cancelamento de NF: 24 h · cobrança ("ainda não recebi"): 24 h · pedido de NF: 48 h.
- Dias corridos: sábado, domingo e feriado contam.
- O relógio começa quando o hóspede pediu: o 1º e-mail ainda sem resposta da conversa, ou o carimbo do formulário.
- O Painel recebe só "vence" e "horas" e calcula o que falta na tela (o selo anda sozinho entre as atualizações).
"""
import datetime

HORAS = {"corrigir": 24, "cobranca": 24, "pedido": 48}
NOMES = {"corrigir": "correção", "cobranca": "cobrança", "pedido": "pedido"}


def tipo(classes):
    classes = classes or []
    if "corrigir" in classes:
        return "corrigir"
    if "cobranca" in classes:
        return "cobranca"
    return "pedido"


def vencimento(inicio, classes=(), tipo_prazo=None):
    """inicio: datetime ou iso -> {"tipo", "nome", "horas", "vence": iso} | None (sem data)."""
    if isinstance(inicio, str):
        try:
            inicio = datetime.datetime.fromisoformat(inicio[:19])
        except ValueError:
            return None
    if not inicio:
        return None
    t = tipo_prazo or tipo(classes)
    return {"tipo": t, "nome": NOMES[t], "horas": HORAS[t],
            "vence": (inicio + datetime.timedelta(hours=HORAS[t])).isoformat(timespec="seconds")}


def situacao(prazo, agora):
    """-> ("ok" | "perto" | "vencido", horas que faltam (negativo = venceu há)). "perto" = passou da metade."""
    resta = (datetime.datetime.fromisoformat(prazo["vence"]) - agora).total_seconds() / 3600
    return ("vencido" if resta <= 0 else "perto" if resta <= prazo["horas"] / 2 else "ok"), round(resta, 1)
