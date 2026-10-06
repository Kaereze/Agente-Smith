"""O que os robôs de TODOS os PCs fizeram, numa aba só da Planilha Central (Atividade_Robo).

Cada PC só enxerga o próprio Outlook; aqui ele conta pros outros: pedido novo, e-mail do hóspede
recebido, NF enviada, tratativa, Outlook fechado, PC atualizado. O Painel de qualquer PC lê esta aba
e mostra tudo na página Atividade (pedido do usuário, 06/10/2026: "os dados que o PC do Cristian
estiver vendo preciso ver também").
"""
import datetime
import socket

from log_util import configurar_logging

logger = configurar_logging(__name__)

ABA = "Atividade_Robo"
CABECALHO = ["Quando", "PC", "Agente", "Tipo", "Hotel", "Pedido", "Detalhe"]

NOVA_SOLICITACAO = "NOVA_SOLICITACAO"
EMAIL_RECEBIDO = "EMAIL_RECEBIDO"
NF_ENVIADA = "NF_ENVIADA"
NF_DROPBOX = "NF_DROPBOX"
TRATATIVA = "TRATATIVA"
NOTA_UNICA = "NOTA_UNICA"
OUTLOOK_FECHADO = "OUTLOOK_FECHADO"
OUTLOOK_ABERTO = "OUTLOOK_ABERTO"
ATUALIZADO = "ATUALIZADO"
CONFERENCIA = "CONFERENCIA"
FALHA = "FALHA"


def linha(tipo, hotel="", pedido="", detalhe="", agente="", pc=None, quando=None):
    quando = quando or datetime.datetime.now()
    return [quando.isoformat(timespec="seconds"), pc or socket.gethostname(), agente, tipo,
            hotel, str(pedido)[:120], str(detalhe)[:300]]


def registrar(backend, planilha_id, linhas):
    """Anexa na aba (cria se faltar). Nunca derruba quem chamou: o registro é extra."""
    if not linhas:
        return
    try:
        backend.anexar_linhas(planilha_id, ABA, linhas)
    except Exception as e:
        if "not found" in str(e).lower() or "WorksheetNotFound" in type(e).__name__:
            try:
                backend.criar_aba_log(planilha_id, ABA, CABECALHO)
                backend.anexar_linhas(planilha_id, ABA, linhas)
                return
            except Exception as e2:
                e = e2
        logger.warning(f"⚠️ Não consegui registrar {len(linhas)} atividade(s) na Central ({e}).")


def ler(linhas, limite=400):
    """Linhas da aba -> [{quando, pc, agente, tipo, hotel, pedido, detalhe}], mais novas primeiro."""
    saida = []
    for l in (linhas or [])[1:]:
        if not l or not str(l[0]).strip():
            continue
        l = list(l) + [""] * (len(CABECALHO) - len(l))
        saida.append(dict(zip(["quando", "pc", "agente", "tipo", "hotel", "pedido", "detalhe"], l[:7])))
    saida.sort(key=lambda a: a["quando"], reverse=True)
    return saida[:limite]
