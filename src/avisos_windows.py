"""Aviso do Windows (notificação no canto da tela) quando um PC da equipe sai do normal (pedido do usuário,
07/10/2026): PC desligou, Outlook fechou ou a conferência parou, e quando ele volta.

O PC principal avisa sobre todos; os outros, só sobre eles mesmos (a Clara não precisa saber do Bernardo).
Só avisa na MUDANÇA (não repete a cada leitura) e só no horário de trabalho (painel.avisos no config).
"""
import datetime
import subprocess

from log_util import configurar_logging

logger = configurar_logging(__name__)

OK, FORA, OUTLOOK, PARADA = "ok", "fora", "outlook_fechado", "parada"
PADRAO = {"ativo": True, "das": "07:00", "ate": "20:00"}
# AppID do PowerShell: deixa mandar notificação sem instalar nada
_APP_ID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def situacao(p):
    if not p.get("online"):
        return FORA
    if p.get("outlook") == "fechado":
        return OUTLOOK
    if p.get("conferencia_atrasada"):
        return PARADA
    return OK


def texto(p, sit, este_pc):
    """-> (título, mensagem). "no PC de Clara" / "neste PC"."""
    proprio = p["pc"].lower() == este_pc.lower()
    no_pc = "neste PC" if proprio else f"no PC de {p.get('agente') or p['pc']}"
    o_pc = "Este PC" if proprio else f"O PC de {p.get('agente') or p['pc']}"
    if sit == FORA:
        return "PC desligado", f"{o_pc} parou de dar sinal: as caixas de e-mail dele não estão sendo lidas."
    if sit == OUTLOOK:
        return "Outlook fechado", f"O Outlook fechou {no_pc}: o robô parou de ler as caixas de e-mail. Abra o Outlook."
    if sit == PARADA:
        return "Conferência parada", f"A conferência dos e-mails parou {no_pc} (Outlook aberto, sem volta há mais de 10 min)."
    return "Voltou ao normal", f"{o_pc} voltou: Outlook aberto e conferindo os e-mails."


class Avisos:
    def __init__(self):
        self.antes = None   # {pc: situação}; None = ainda não olhou (ao ligar, só memoriza)

    def mudancas(self, pcs, este_pc, principal, agora=None, cfg_avisos=None):
        """-> [(título, texto)] do que mudou desde a última leitura e deve virar aviso."""
        cfg = {**PADRAO, **(cfg_avisos or {})}
        agora = agora or datetime.datetime.now()
        atual = {p["pc"]: situacao(p) for p in pcs if principal or p["pc"].lower() == este_pc.lower()}
        antes, self.antes = self.antes, atual
        if antes is None or not cfg["ativo"] or not (cfg["das"] <= agora.strftime("%H:%M") < cfg["ate"]):
            return []
        avisos = []
        for p in pcs:
            pc = p["pc"]
            if pc not in atual or pc not in antes or atual[pc] == antes[pc]:
                continue
            if atual[pc] == OK and antes[pc] == FORA:
                continue   # PC ligando de manhã: não é novidade pra avisar
            avisos.append(texto(p, atual[pc], este_pc))
        return avisos


def _xml(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            .replace("'", "&apos;"))


def mostrar(titulo, mensagem):
    """Notificação do Windows, sem esperar (não trava o Painel). Falhou? Fica só no log."""
    xml = (f"<toast><visual><binding template='ToastGeneric'><text>{_xml('Painel Fiscal · ' + titulo)}</text>"
           f"<text>{_xml(mensagem)}</text></binding></visual></toast>")
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($env:AVISO_XML);"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:AVISO_APP)"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    import os
    env = dict(os.environ, AVISO_XML=xml, AVISO_APP=_APP_ID)   # texto pelo ambiente: sem problema de aspas
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                         creationflags=_SEM_JANELA, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"🔔 Aviso: {titulo} — {mensagem}")
    except OSError as e:
        logger.warning(f"⚠️ Não consegui mostrar o aviso do Windows ({e}): {titulo} — {mensagem}")


if __name__ == "__main__":
    from console_utf8 import garantir_utf8
    garantir_utf8()
    mostrar("Teste", "Se você está lendo isto, os avisos do Painel funcionam neste PC.")
