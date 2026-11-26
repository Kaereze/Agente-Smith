"""Relatório do Mail Analytics enviado pelo Outlook do PC principal, pela conta do CECOMTUR, a pedido do notebook administrador.

Usuário, 26/11/2026: "esse computador não pode abrir o Outlook dele de jeito nenhum"; "o relatório [vai] pros chefes do
notebook, mas esse notebook, como tem conexão pelo firewall com os outros PCs, vai fazer uma requisição de envio de e-mail
pelo e-mail do cecomtur mesmo para o envio do relatório consolidado".

O notebook monta o relatório (lendo só a planilha) e decide quem recebe (os chefes do destinatarios.json dele). Ele manda o
pedido assinado e cifrado pela rede do escritório (/rede/enviar_relatorio, mesmo protocolo do rede_local). Este PC manda
pelo próprio Outlook, da conta do CECOMTUR.

Segurança, além da assinatura do rede_local (só os PCs do escritório têm o segredo):
- Só o PC principal atende (os outros recusam com 403).
- Só sai da conta do CECOMTUR deste Outlook: conta pedida que não está aqui, ou mais de uma conta "cecomtur" sem dizer
  qual, recusa sem mandar.
- No máximo MAX_DESTINATARIOS endereços. Lista opcional "relatorio_pela_rede.destinatarios_permitidos" no
  config.local.json: se existir, só esses podem receber.
- O pedido leva um id único: repetido (o notebook tentou de novo depois de um tempo-limite) não manda de novo.
"""
import base64
import datetime
import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

from sistema import armazem
from sistema.log_util import configurar_logging

logger = configurar_logging(__name__)

ARQUIVO_FEITOS = "relatorios_pela_rede.json"
ID_PEDIDO = re.compile(r"MA-[0-9a-f]{16,40}")
EMAIL = re.compile(r"[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+")
CONTA_PADRAO = "cecomtur"
DISPID_SEND_USING_ACCOUNT = 64209   # MailItem.SendUsingAccount (mesmo truque do envio_pc_dono)
GUARDAR_FEITOS_DIAS = 30
MAX_DESTINATARIOS = 20
MAX_ANEXOS = 5
EXTENSOES_ANEXO = {".html", ".htm", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv"}

_trava = threading.Lock()


def _caminho_feitos():
    return armazem.caminho(ARQUIVO_FEITOS)


def _emails(valor):
    if isinstance(valor, str):
        valor = [valor]
    return [str(e).strip().lower() for e in (valor or []) if str(e).strip() and not str(e).strip().startswith("#")]


def destinatarios_permitidos(cfg):
    """Lista opcional do config.local.json; vazia = quem o notebook mandar (até MAX_DESTINATARIOS)."""
    return set(_emails((cfg.get("relatorio_pela_rede") or {}).get("destinatarios_permitidos")))


def _ler_feitos():
    try:
        return json.loads(_caminho_feitos().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_feitos(feitos, agora):
    limite = (agora - datetime.timedelta(days=GUARDAR_FEITOS_DIAS)).isoformat(timespec="seconds")
    feitos = {k: v for k, v in feitos.items() if str(v) >= limite}
    caminho = _caminho_feitos()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")


def conta_remetente(ns, pedida):
    """A conta do Outlook daqui que manda: endereço exato pedido, ou a única que contém o texto pedido (padrão "cecomtur")."""
    pedida = str(pedida or CONTA_PADRAO).strip().lower()
    contas = [(str(getattr(c, "SmtpAddress", "") or "").strip().lower(), c) for c in ns.Accounts]
    exata = [c for e, c in contas if e == pedida]
    if exata:
        return exata[0]
    parecidas = [(e, c) for e, c in contas if pedida in e]
    if len(parecidas) == 1:
        return parecidas[0][1]
    if not parecidas:
        raise PermissionError(f"a conta '{pedida}' não está no Outlook deste PC")
    raise PermissionError(f"mais de uma conta com '{pedida}' neste Outlook ({', '.join(e for e, _ in parecidas)}): "
                          f"diga qual em conta_remetente no config/envio_pela_rede.json do notebook")


def validar(corpo, permitidos):
    """-> (id, para, cc, assunto, html, anexos) ou levanta PermissionError (o rede_local responde 403)."""
    id_pedido = str(corpo.get("id") or "")
    if not ID_PEDIDO.fullmatch(id_pedido):
        raise PermissionError("pedido sem id do Mail Analytics")
    para, cc = _emails(corpo.get("para")), _emails(corpo.get("cc"))
    if not para:
        raise PermissionError("pedido sem destinatário")
    if len(para) + len(cc) > MAX_DESTINATARIOS:
        raise PermissionError(f"destinatários demais (máximo {MAX_DESTINATARIOS})")
    for e in para + cc:
        if not EMAIL.fullmatch(e):
            raise PermissionError(f"endereço inválido: {e}")
        if permitidos and e not in permitidos:
            raise PermissionError(f"{e} não está em relatorio_pela_rede.destinatarios_permitidos deste PC")
    assunto, html = str(corpo.get("assunto") or "").strip(), str(corpo.get("html") or "")
    if not assunto or not html.strip():
        raise PermissionError("pedido sem assunto ou sem texto")
    anexos = list(corpo.get("anexos") or [])
    if len(anexos) > MAX_ANEXOS:
        raise PermissionError("anexos demais")
    limpos = []
    for a in anexos:
        nome = Path(str((a or {}).get("nome") or "").replace("\\", "/")).name
        if not nome or Path(nome).suffix.lower() not in EXTENSOES_ANEXO:
            raise PermissionError(f"tipo de anexo não aceito: {nome or '(sem nome)'}")
        try:
            limpos.append((nome, base64.b64decode(str(a.get("base64") or ""), validate=True)))
        except ValueError as e:
            raise PermissionError(f"anexo {nome} corrompido") from e
    return id_pedido, para, cc, assunto, html, limpos


TAREFA_CONSOLIDADO = "MailAnalytics_RelatorioConsolidado"


def desligar_consolidado_aqui(rodar=subprocess.run):
    """O notebook administrador manda o consolidado (usuário, 26/11/2026: "desliga a tarefa no PC do João pela rede"):
    desliga a tarefa agendada do Mail Analytics DESTE PC, senão ele manda antes, pelo caminho antigo. Só essa tarefa,
    nome fixo: o pedido da rede não escolhe tarefa nem comando. -> {"pc", "tarefa", "estado"} ("Disabled", "ausente")"""
    script = (f"$t = Get-ScheduledTask -TaskName '{TAREFA_CONSOLIDADO}' -ErrorAction SilentlyContinue; "
              f"if (-not $t) {{ 'ausente' }} else {{ Disable-ScheduledTask -TaskName '{TAREFA_CONSOLIDADO}' | Out-Null; "
              f"(Get-ScheduledTask -TaskName '{TAREFA_CONSOLIDADO}').State }}")
    r = rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
              timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    estado = (r.stdout or "").strip().splitlines()[-1:] or [""]
    resposta = {"pc": socket.gethostname(), "tarefa": TAREFA_CONSOLIDADO, "estado": estado[0]}
    if r.returncode != 0 or estado[0] not in ("Disabled", "ausente"):
        resposta["erro"] = ((r.stderr or "").strip() or f"saída {r.returncode}")[:200]
    logger.info(f"🔕 Tarefa {TAREFA_CONSOLIDADO} a pedido do notebook administrador: {resposta.get('erro') or estado[0]}")
    return resposta


def enviar_aqui(app, corpo, permitidos, agora=None):
    """No PC principal: manda o relatório pelo Outlook daqui, da conta do CECOMTUR. Pedido repetido não manda de novo."""
    id_pedido, para, cc, assunto, html, anexos = validar(corpo, permitidos)
    agora = agora or datetime.datetime.now()
    eu = socket.gethostname()
    with _trava:
        feitos = _ler_feitos()
        if id_pedido in feitos:
            return {"pc": eu, "enviado": True, "ja_estava": True}
        conta = conta_remetente(app.GetNamespace("MAPI"), corpo.get("conta_de"))
        pasta = Path(tempfile.mkdtemp(prefix="relatorio_rede_"))
        try:
            mail = app.CreateItem(0)   # olMailItem
            mail.To = "; ".join(para)
            if cc:
                mail.CC = "; ".join(cc)
            mail.Subject = assunto
            mail.HTMLBody = html
            for nome, dados in anexos:
                caminho = pasta / nome
                caminho.write_bytes(dados)
                mail.Attachments.Add(str(caminho))
            mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
            mail.Send()
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        feitos[id_pedido] = agora.isoformat(timespec="seconds")
        _gravar_feitos(feitos, agora)
    de = str(getattr(conta, "SmtpAddress", "") or "?")
    logger.info(f"📤 Relatório do Mail Analytics enviado daqui, pela conta {de}, a pedido do notebook administrador "
                f"({id_pedido}, {len(para)} destinatário(s){f', {len(cc)} em cópia' if cc else ''})")
    return {"pc": eu, "conta": de, "enviado": True, "ja_estava": False}
