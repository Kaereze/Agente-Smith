"""Outlook: responde "Sim" sozinho ao "Aviso de Segurança da Internet" do nome do certificado (usuário, 09/10/2026).

As caixas enviam por smtp.<domínio do hotel>, mas o certificado do provedor tem outro nome: o Outlook abre o aviso
"O nome principal do destino está incorreto. Deseja continuar usando este servidor?" e, enquanto ninguém responde,
a fila de envio do PC inteiro para (já ficou 1 dia parada). O vigia do conferente olha a cada 20 s e clica "Sim".

Trava de segurança: só responde quando o ÚNICO problema é o nome. Certificado vencido, revogado ou de emissor não
confiável (o que pode ser golpe) não é aceito: fica a janela pra uma pessoa olhar, e o log avisa.
O clique é uma mensagem pro botão (não move o mouse nem rouba o foco de quem está usando o PC).
"""
import os

from log_util import configurar_logging

logger = configurar_logging("aviso_certificado")

TITULOS = ("aviso de segurança da internet", "internet security warning")
MOTIVO_ACEITO = ("nome principal do destino está incorreto", "nome principal do destino esta incorreto",
                 "target principal name is incorrect", "name on the security certificate is invalid",
                 "nome no certificado de segurança é inválido")
MOTIVOS_PERIGO = ("expir", "venc", "revog", "revoked", "não é confiável", "nao e confiavel", "not trusted",
                  "não confiável", "untrusted", "autoridade", "authority")
BOTAO_SIM = 6            # IDYES
WM_COMMAND, BN_CLICKED = 0x0111, 0


def decidir(texto):
    """Texto do aviso -> "aceitar" (só o nome está diferente) | "suspeito" (outro problema) | "outro" (não é esse aviso)."""
    t = " ".join((texto or "").lower().split())
    if not any(m in t for m in MOTIVO_ACEITO):
        return "suspeito" if "certificado" in t or "certificate" in t else "outro"
    return "suspeito" if any(p in t for p in MOTIVOS_PERIGO) else "aceitar"


def _exe_da_janela(h):
    import win32api
    import win32con
    import win32process
    _, pid = win32process.GetWindowThreadProcessId(h)
    try:
        proc = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        return os.path.basename(win32process.GetModuleFileNameEx(proc, 0)).lower()
    except Exception:
        return ""


def responder_avisos():
    """Procura os avisos abertos do Outlook e responde. -> {"aceitos": n, "suspeitos": [texto]}"""
    import win32gui
    avisos = []

    def topo(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770" \
                and win32gui.GetWindowText(h).strip().lower() in TITULOS:
            avisos.append(h)
        return True
    win32gui.EnumWindows(topo, None)
    saida = {"aceitos": 0, "suspeitos": []}
    for h in avisos:
        if _exe_da_janela(h) != "outlook.exe":
            continue
        textos, sim = [], None

        def filho(c, _):
            nonlocal sim
            classe, texto = win32gui.GetClassName(c), win32gui.GetWindowText(c)
            if classe == "Static" and texto:
                textos.append(texto)
            if classe == "Button" and (win32gui.GetDlgCtrlID(c) == BOTAO_SIM or texto.replace("&", "").lower() in ("sim", "yes")):
                sim = c
            return True
        win32gui.EnumChildWindows(h, filho, None)
        texto = " ".join(textos)
        decisao = decidir(texto)
        if decisao == "aceitar" and sim:
            win32gui.PostMessage(h, WM_COMMAND, (BN_CLICKED << 16) | BOTAO_SIM, sim)
            saida["aceitos"] += 1
            logger.info("🔐 Outlook: aviso de certificado (nome do servidor diferente) respondido com \"Sim\" automaticamente")
        elif decisao == "suspeito":
            saida["suspeitos"].append(texto[:300])
            logger.warning(f"⚠️ Outlook: aviso de certificado DIFERENTE do de sempre — não cliquei, alguém precisa olhar: "
                           f"{texto[:200]}")
    return saida
