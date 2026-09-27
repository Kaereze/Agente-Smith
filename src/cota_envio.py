"""Cota do servidor de e-mail (KingHost 250/h): conta os envios da última hora."""
import datetime
import json

JANELA = datetime.timedelta(hours=1)
HISTORICO = datetime.timedelta(hours=24)
MAX_ITENS_OLHADOS = 2000   # 24h de envio cabem com folga (limite é 250/h)


def _data_outlook(valor):
    """Contas POP desta rede: SentOn vem com a hora LOCAL marcada como UTC — só tira o fuso."""
    return valor.replace(tzinfo=None) if getattr(valor, "tzinfo", None) else valor


def envios_das_ultimas_24h(pasta_enviados, agora):
    """[(hora_do_envio, n_destinatarios)] dos Itens Enviados, do mais novo pro mais velho."""
    itens = pasta_enviados.Items
    itens.Sort("[SentOn]", True)
    envios = []
    for i, item in enumerate(itens):
        if i >= MAX_ITENS_OLHADOS:
            break
        try:
            quando = _data_outlook(item.SentOn)
        except Exception:
            continue   # reunião, relatório de entrega etc.
        if quando > agora + datetime.timedelta(minutes=5):
            continue   # relógio estranho: ignora
        if agora - quando > HISTORICO:
            break
        try:
            destinatarios = max(int(item.Recipients.Count), 1)
        except Exception:
            destinatarios = 1
        envios.append((quando, destinatarios))
    return envios


def calcular_cota(envios, limite_por_hora, agora):
    """Conta pura (testável): quanto foi usado na última hora e quando libera mais."""
    na_janela = sorted((q, n) for q, n in envios if agora - q < JANELA)
    usados = sum(n for _, n in na_janela)
    sobra = max(limite_por_hora - usados, 0)
    # Quando o envio mais antigo da janela fizer 1 hora, a cota dele volta
    libera = (na_janela[0][0] + JANELA) if na_janela else None
    por_hora = []
    for h in range(23, -1, -1):
        fim = agora - datetime.timedelta(hours=h)
        ini = fim - JANELA
        por_hora.append({"hora": ini.strftime("%H:%M"),
                         "n": sum(n for q, n in envios if ini <= q < fim)})
    return {
        "limite_hora": limite_por_hora,
        "usados_hora": usados,
        "sobra_hora": sobra,
        "usados_24h": sum(n for q, n in envios if agora - q < HISTORICO),
        "proxima_liberacao": libera.strftime("%H:%M") if libera else "",
        "por_hora": por_hora,
        "atualizado": agora.astimezone().isoformat(timespec="seconds"),
    }


def medir(namespace, cfg, agora=None):
    """Mede a cota da conta remetente e devolve o texto (JSON) pra aba Status."""
    agora = agora or datetime.datetime.now()
    cota = cfg.get("cota_envio", {})
    remetente = (cfg.get("conta_remetente") or "").strip().lower()
    conta = next((c for c in namespace.Accounts if (c.SmtpAddress or "").strip().lower() == remetente), None)
    if conta is None:
        raise RuntimeError(f"a conta {remetente} não está no Outlook deste PC")
    pasta = conta.DeliveryStore.GetDefaultFolder(5)   # 5 = Itens Enviados
    r = calcular_cota(envios_das_ultimas_24h(pasta, agora), int(cota.get("limite_por_hora", 250)), agora)
    r.update(conta=remetente, provedor=cota.get("provedor", ""))
    return json.dumps(r, ensure_ascii=False)
