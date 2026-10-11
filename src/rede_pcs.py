"""Os PCs da equipe conversando pela Planilha Central (pedido do usuário, 06/10/2026: "mexer nos outros
PCs sem precisar ficar trocando de máquina").

- PCs_Painel: cada Painel publica a cada minuto quem é, as caixas, se o Outlook está aberto, a versão
  do código, o papel e a última conferência do Outlook.
- Comandos_PC: um Painel pede, o do PC de destino executa e responde ("atualizar" = puxar a versão
  nova do GitHub e reiniciar). Para "TODOS", cada PC responde por si.
"""
import datetime
import json
import subprocess
import uuid

import saude
from config import PASTA_ESTADO

ABA_COMANDOS = "Comandos_PC"
CAB_COMANDOS = ["Quando", "ID", "Para", "Comando", "Por", "Resposta"]
COMANDOS = {"atualizar"}
VALIDADE_COMANDO_MIN = 60          # pedido mais velho que isso não é executado (PC estava desligado)
PC_ONLINE_SEGUNDOS = 180
CONFERENCIA_ATRASADA_MIN = 10      # conferente parado: sem volta do Outlook há mais que isso
CAMINHO_STATUS_CONFERENCIA = PASTA_ESTADO / "confirmar_status.json"


def pedido(para, comando, por, quando=None):
    quando = quando or datetime.datetime.now()
    return [quando.isoformat(timespec="seconds"), "CMD-" + uuid.uuid4().hex[:8].upper(), para, comando, por, ""]


def resposta(id_comando, pc, comando, texto, quando=None):
    quando = quando or datetime.datetime.now()
    return [quando.isoformat(timespec="seconds"), id_comando, pc, comando, pc, texto[:200]]


def _data(texto):
    """Aceita o que a planilha devolve: "2026-10-07T09:10:19", "2026-10-07 9:10:19" (o Sheets tira o zero da
    hora ao reformatar) e "07/10/2026 09:10:19"."""
    texto = str(texto).strip()[:19]
    try:
        return datetime.datetime.fromisoformat(texto)
    except ValueError:
        pass
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def pendentes(linhas, pc, agora=None):
    """Pedidos pra este PC (ou TODOS) ainda sem resposta dele. -> [(id, comando, por)]"""
    agora = agora or datetime.datetime.now()
    pedidos, respondidos = [], set()
    for l in (linhas or [])[1:]:
        l = list(l) + [""] * (len(CAB_COMANDOS) - len(l))
        quando, id_c, para, comando, por, resp = (str(v).strip() for v in l[:6])
        if resp:
            if para.lower() == pc.lower():
                respondidos.add(id_c)
        elif para.lower() in (pc.lower(), "todos") and comando in COMANDOS:
            dt = _data(quando)
            if dt and agora - dt <= datetime.timedelta(minutes=VALIDADE_COMANDO_MIN):
                pedidos.append((id_c, comando, por))
    return [p for p in pedidos if p[0] not in respondidos]


def outlook_aberto():
    """Outlook clássico rodando neste PC (é ele que o robô lê)."""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/NH"], capture_output=True, text=True,
                           timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "outlook.exe" in (r.stdout or "").lower()
    except Exception:
        return None


def ultima_conferencia():
    """'2026-10-06T17:40:00|2 NF · 1 tratativa · 3 recebido(s)' da última volta do Outlook deste PC."""
    try:
        s = json.load(open(CAMINHO_STATUS_CONFERENCIA, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return ""
    return f"{s.get('quando', '')}|{s.get('nfs', 0)} NF · {s.get('tratativas', 0)} tratativa · {s.get('recebidos', 0)} recebido(s)"


def ler_pcs(linhas, agora=None):
    """Linhas da aba PCs_Painel -> [{pc, agente, caixas, online, visto, outlook, versao, papel, conferencia,
    conferencia_atrasada}]"""
    agora = agora or datetime.datetime.now()
    pcs = []
    for l in (linhas or [])[1:]:
        if not l or not str(l[0]).strip():
            continue
        l = [str(v).strip() for v in l] + [""] * 12
        visto = _data(l[3])
        online = bool(visto and (agora - visto).total_seconds() < PC_ONLINE_SEGUNDOS)
        conf_quando, _, conf_resumo = l[7].partition("|")
        conf_dt = _data(conf_quando)
        pcs.append({"pc": l[0], "agente": l[1], "caixas": len([c for c in l[2].split(",") if c]),
                    "online": online, "visto": l[3], "outlook": l[4], "versao": l[5], "papel": l[6],
                    "conferencia": conf_quando, "conferencia_resumo": conf_resumo,
                    "rede": l[8], "cota": l[9], "uso": l[10], "saude": saude.ler_coluna(l[11]),   # "aberto|E-mails|hh:mm" = Painel aberto agora, em qual tela   # "ip:porta" (busca ao vivo) e "leituras/escritas" no último minuto
                    # sem nenhuma volta ainda (PC acabou de ligar) não é "parada"
                    "conferencia_atrasada": bool(online and l[4] == "aberto" and conf_dt and
                                                 (agora - conf_dt).total_seconds() > CONFERENCIA_ATRASADA_MIN * 60)})
    return sorted(pcs, key=lambda p: (not p["online"], p["agente"], p["pc"]))
