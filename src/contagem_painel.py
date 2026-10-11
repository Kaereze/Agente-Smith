"""Contagem do fim de semana pelo Painel (usuário, 11/10/2026).

No fim de semana só João e Cristian trabalham, e o Mail Analytics deles guarda sexta e sábado e só grava na planilha,
na manhã de segunda, UMA linha com sexta + sábado + domingo somados (com a data do domingo). Até lá a planilha fica
sem esses dias. O Painel conta esses dias "por trás dos panos" — com as mesmas regras do Mail Analytics, simplificadas
— e o relatório da Gerência usa essa contagem ENQUANTO o Mail Analytics não grava o domingo. Quando a linha do
domingo aparece, vale a dele (nunca soma as duas: não conta em dobro). A planilha do Mail Analytics não é tocada:
a contagem fica na aba ContagemPainel_<PC> da Central (abas de passagem, 14 dias).

Regras (iguais às do Mail Analytics, sem o histórico de reenvio):
- Recebidos: e-mails da Caixa de Entrada recebidos no dia (fora as solicitações do robô).
- Enviados: Itens Enviados no dia (fora os e-mails do robô).
- NFs: números de NF diferentes ("NF 123 - ...") em e-mails novos (não "RE:"/"ENC:") enviados no dia.
- Ligações: e-mails enviados com "ligacao"/"ligação" no assunto (1 por conversa).
"""
import datetime
import json
import re
import socket

from arquivos import salvar_json
from config import PASTA_ESTADO
from log_util import configurar_logging

logger = configurar_logging("contagem_painel")

AGENTES_FIM_DE_SEMANA = ("João", "Cristian")
DIAS_DO_BLOCO = (4, 5, 6)          # sexta, sábado, domingo (o Mail Analytics soma os 3 na linha do domingo)
PREFIXO_ABA = "ContagemPainel_"
CAB = ["Data", "Agente", "Hotel", "Caixa", "Recebidos", "Enviados", "NFs", "Ligações", "Contado em"]
MANTER_DIAS = 14
RECONTAR_HOJE_MIN = 60
CAMINHO = PASTA_ESTADO / "contagem_painel.json"
_NF = re.compile(r"\bNF\s*n?[º°o.]*\s*(\d{2,7})\b", re.I)
_RESPOSTA = re.compile(r"^\s*(re|res|enc|fw|fwd|encaminhad[ao])\s*[:\]]", re.I)


def agente_deste_pc():
    """Quem trabalha neste PC (o mesmo nome que o Painel mostra): estado/app.json, senão a identidade do PC."""
    try:
        nome = json.load(open(PASTA_ESTADO / "app.json", encoding="utf-8")).get("agente")
        if nome:
            return nome
    except (OSError, ValueError):
        pass
    try:
        import identidade
        return identidade.ler().get("agente", "")
    except Exception:
        return ""


def nome_aba(pc=None):
    return PREFIXO_ABA + (pc or socket.gethostname())


def _data(valor):
    try:
        return datetime.datetime(valor.year, valor.month, valor.day, valor.hour, valor.minute, valor.second)
    except Exception:
        return None


def _do_robo(item):
    return "Código de envio: NF-" in str(getattr(item, "Body", "") or "")[:20000]


def contar_dia(namespace, caixas, dia):
    """Outlook deste PC -> {caixa: {"hotel", "recebidos", "enviados", "nfs", "ligacoes"}} do dia (só lê)."""
    ini = datetime.datetime(dia.year, dia.month, dia.day)
    fim = ini + datetime.timedelta(days=1)
    filtro = lambda campo: f"[{campo}] >= '{ini:%d/%m/%Y %H:%M}' AND [{campo}] < '{fim:%d/%m/%Y %H:%M}'"
    saida = {}
    for conta in namespace.Accounts:
        caixa = str(getattr(conta, "SmtpAddress", "") or "").strip().lower()
        if caixa not in caixas:
            continue
        c = {"hotel": caixas[caixa], "recebidos": 0, "enviados": 0, "nfs": 0, "ligacoes": 0}
        try:
            loja = conta.DeliveryStore
            for item in loja.GetDefaultFolder(6).Items.Restrict(filtro("ReceivedTime")):
                if getattr(item, "Class", 0) == 43 and not _do_robo(item):
                    c["recebidos"] += 1
            nfs, conversas = set(), set()
            for item in loja.GetDefaultFolder(5).Items.Restrict(filtro("SentOn")):
                if getattr(item, "Class", 0) != 43 or _do_robo(item):
                    continue
                c["enviados"] += 1
                assunto = str(getattr(item, "Subject", "") or "")
                if not _RESPOSTA.match(assunto):
                    nfs |= set(_NF.findall(assunto))
                if "ligacao" in assunto.lower().replace("ç", "c").replace("ã", "a"):
                    conversas.add(str(getattr(item, "ConversationID", "") or getattr(item, "EntryID", "")))
            c["nfs"], c["ligacoes"] = len(nfs), len(conversas)
        except Exception as e:
            logger.debug(f"contagem de {caixa} em {dia}: {e}")
            continue
        saida[caixa] = c
    return saida


class Contagem:
    """Guarda a contagem de cada dia do bloco (sexta a domingo) e publica na aba ContagemPainel_<PC>."""

    def __init__(self, relogio=datetime.datetime.now):
        self.relogio = relogio
        try:
            self.estado = json.load(open(CAMINHO, encoding="utf-8"))
        except (OSError, ValueError):
            self.estado = {}

    def dias_a_contar(self, agora):
        """Dias do bloco nos últimos 3 dias: hoje (parcial, de hora em hora) e os que ainda não foram fechados
        (contados de novo uma vez depois das 6h do dia seguinte, quando a contagem fica definitiva)."""
        hoje = agora.date()
        saida = []
        for k in range(0, 4):
            dia = hoje - datetime.timedelta(days=k)
            if dia.weekday() not in DIAS_DO_BLOCO:
                continue
            reg = self.estado.get(dia.isoformat())
            contado = datetime.datetime.fromisoformat(reg["contado_em"]) if reg else None
            fechamento = datetime.datetime(dia.year, dia.month, dia.day) + datetime.timedelta(days=1, hours=6)
            if dia == hoje:
                if not contado or agora - contado > datetime.timedelta(minutes=RECONTAR_HOJE_MIN):
                    saida.append(dia)
            elif (not contado or contado < fechamento) and agora >= fechamento:
                saida.append(dia)
        return saida

    def talvez(self, namespace, caixas, agente, backend=None, central=None):
        """Chamado pelo conferente (a cada ~2 min). Só nos PCs do João e do Cristian. -> True se mudou."""
        if agente not in AGENTES_FIM_DE_SEMANA:
            return False
        agora = self.relogio()
        dias = self.dias_a_contar(agora)
        if not dias:
            return False
        for dia in dias:
            self.estado[dia.isoformat()] = {"contado_em": agora.isoformat(timespec="seconds"),
                                            "caixas": contar_dia(namespace, caixas, dia)}
            total = sum(c["recebidos"] for c in self.estado[dia.isoformat()]["caixas"].values())
            logger.info(f"🧮 Contagem do fim de semana ({dia:%a %d/%m}): {total} e-mail(s) recebido(s) nas caixas de {agente}")
        corte = (agora.date() - datetime.timedelta(days=MANTER_DIAS)).isoformat()
        self.estado = {d: v for d, v in self.estado.items() if d >= corte}
        salvar_json(CAMINHO, self.estado)
        if backend and central:
            try:
                backend.substituir_aba(central, nome_aba(), self.linhas(agente))
            except Exception as e:
                logger.warning(f"⚠️ Não consegui publicar a contagem do fim de semana ({e})")
        return True

    def linhas(self, agente):
        saida = [CAB]
        for dia in sorted(self.estado, reverse=True):
            reg = self.estado[dia]
            for caixa, c in sorted(reg.get("caixas", {}).items()):
                saida.append([dia, agente, c["hotel"], caixa, c["recebidos"], c["enviados"], c["nfs"], c["ligacoes"],
                              reg["contado_em"]])
        return saida


def ler_abas(linhas_por_aba):
    """Abas ContagemPainel_<PC> -> {agente: [{"dia", "hotel", recebidos, enviados, ligacoes, subst_canc, nfs}]}"""
    saida = {}
    for linhas in linhas_por_aba:
        for l in (linhas or [])[1:]:
            if not l or len(l) < 8:
                continue
            try:
                dia = datetime.date.fromisoformat(str(l[0])[:10])
            except ValueError:
                continue
            num = lambda v: int(float(str(v or 0)))
            saida.setdefault(str(l[1]), []).append({"dia": dia, "hotel": str(l[2]), "recebidos": num(l[4]), "enviados": num(l[5]),
                                                    "nfs": num(l[6]), "ligacoes": num(l[7]), "subst_canc": 0})
    return saida
