"""Aba "Agentes do Smith" (28/10/2026, desenho aprovado pelo João): o estado ao vivo dos agentes no mapa do sistema.

Só diz o que o Painel JÁ SABE de verdade, a partir da aba PCs_Painel (cada PC publica a cada minuto): se o PC está
ligado, a versão do código, o Outlook, a última conferência, a rede local e a saúde (cópia dos hotéis e robô de envio,
que só o PC principal publica). Agente sem sinal real NÃO entra aqui: a tela o mostra como "sem sinal ao vivo", em vez
de inventar um estado. Só LÊ: não grava nada, não pede nada a nenhum PC.

Estados: "ok" | "atencao" | "parado" | "desligado". Resposta de estado(): {"atualizado", "pcs_total", "pcs_ligados",
"agentes": {id_do_agente: [{"pc": agente, "est": estado, "texto": frase}]}}. Os ids são os blocos do mapa
(app_ui/agentes/mapa.html), que são os nomes dos módulos de src/.
"""
import datetime

import rede_pcs

COPIA_ATENCAO_MIN = 30      # cópia dos hotéis e robô de envio rodam de 10 em 10 min: passou de 30 já merece olhar
COPIA_PARADA_MIN = 120      # duas horas sem rodar: parado
OUTLOOK_OK = "aberto"


def _minutos(texto, agora):
    """Minutos desde `texto` (data da planilha), ou None se não der para ler."""
    quando = rede_pcs._data(texto) if texto else None
    return None if quando is None else max(0, int((agora - quando).total_seconds() // 60))


def _faz(minutos):
    if minutos is None:
        return "em horário desconhecido"
    if minutos < 1:
        return "agora há pouco"
    if minutos < 60:
        return f"há {minutos} min"
    return f"há {minutos // 60} h {minutos % 60:02d} min"


def _hora(texto):
    quando = rede_pcs._data(texto) if texto else None
    return quando.strftime("%H:%M") if quando else "?"


def _por_idade(minutos, rotulo):
    """est e frase de um agente que roda de tempos em tempos (cópia e robô de envio)."""
    if minutos is None:
        return None
    if minutos >= COPIA_PARADA_MIN:
        return "parado", f"{rotulo} {_faz(minutos)}. Era esperado a cada 10 min."
    if minutos >= COPIA_ATENCAO_MIN:
        return "atencao", f"{rotulo} {_faz(minutos)}. Era esperado a cada 10 min."
    return "ok", f"{rotulo} {_faz(minutos)}."


def estado(pcs, agora=None):
    """pcs: o que rede_pcs.ler_pcs devolve (uma linha por PC)."""
    agora = agora or datetime.datetime.now()
    agentes = {}

    def pe(id_agente, pc, est, texto):
        agentes.setdefault(id_agente, []).append({"pc": pc.get("agente") or pc.get("pc", "?"), "est": est, "texto": texto})

    ligados = [p for p in pcs if p.get("online")]
    versoes = sorted({str(p.get("versao", "")).lstrip("'") for p in ligados if str(p.get("versao", "")).lstrip("'")})
    maior = versoes[-1] if versoes else ""
    for p in pcs:
        visto = _faz(_minutos(p.get("visto"), agora))
        if not p.get("online"):
            hora = _hora(p.get("visto"))
            fora = "PC sem sinal." if hora == "?" else f"PC sem sinal desde as {hora}."
            for id_agente in ("app_servidor", "rede_pcs", "saude", "atualizador", "outlook_vivo", "conferente", "rede_local"):
                pe(id_agente, p, "desligado", fora)
            continue
        pe("app_servidor", p, "ok", f"Publicou o estado {visto}.")
        pe("rede_pcs", p, "ok", f"Publica a cada minuto; última vez {visto}.")
        presos = int(p.get("saude", {}).get("saida") or 0)
        if presos:
            pe("saude", p, "atencao", f"{presos} e-mail(s) preso(s) na Caixa de Saída do Outlook.")
        else:
            pe("saude", p, "ok", f"Sem aviso. Publicou {visto}.")
        versao = str(p.get("versao", "")).lstrip("'")
        if versao and maior and versao != maior:
            pe("atualizador", p, "atencao", f"Na versão {versao}; a mais nova entre os PCs é {maior}.")
        elif versao:
            pe("atualizador", p, "ok", f"Na versão {versao}.")
        outlook = str(p.get("outlook", "")).strip()
        if outlook == OUTLOOK_OK:
            pe("outlook_vivo", p, "ok", "Outlook aberto, com janela.")
        elif outlook == "fechado":
            pe("outlook_vivo", p, "parado", "Outlook fechado: nenhum e-mail entra nem sai deste PC.")
        elif outlook:
            pe("outlook_vivo", p, "atencao", f"Outlook {outlook}: não envia nem recebe e-mail.")
        if p.get("conferencia_atrasada"):
            pe("conferente", p, "atencao", f"Sem volta do Outlook há mais de {rede_pcs.CONFERENCIA_ATRASADA_MIN} min.")
        elif p.get("conferencia"):
            resumo = f" ({p['conferencia_resumo']})" if p.get("conferencia_resumo") else ""
            pe("conferente", p, "ok", f"Conferiu às {_hora(p['conferencia'])}{resumo}.")
        if p.get("rede"):
            pe("rede_local", p, "ok", f"Escutando em {p['rede']}.")
        else:
            pe("rede_local", p, "atencao", "Este PC não publicou o endereço da rede local.")
        if p.get("papel") == "principal":
            copia = _por_idade(_minutos(p.get("saude", {}).get("copia"), agora), "Última cópia dos hotéis")
            if copia:
                pe("sincronizar", p, *copia)
            robo = _por_idade(_minutos(p.get("saude", {}).get("robo"), agora), "Último envio do robô")
            if robo:
                pe("main", p, *robo)
    return {"atualizado": agora.isoformat(timespec="seconds"), "pcs_total": len(pcs), "pcs_ligados": len(ligados), "agentes": agentes}
