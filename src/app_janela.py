"""Janela do Painel Notas Fiscais: aplicativo próprio (pywebview + WebView2), sem navegador.

    pythonw src\\app_janela.py

Garante o servidor em segundo plano (app_servidor --sem-janela), espera ele responder e abre a
janela. Se a janela já estiver aberta, só traz ela pra frente.
"""
import ctypes
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PASTA_ESTADO, PASTA_PROJETO

PORTA = 8765
TITULO = "Painel Notas Fiscais"
ICONE = PASTA_PROJETO / "app_ui" / "icone.ico"
APP_ID = "RedeAndrade.PainelNotasFiscais"   # agrupa na barra de tarefas como app próprio, não como Python


def servidor_no_ar():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORTA)) == 0


def garantir_servidor(timeout=30):
    if servidor_no_ar():
        return True
    pythonw = PASTA_PROJETO / ".venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen([str(pythonw), str(PASTA_PROJETO / "src" / "app_servidor.py"), "--sem-janela"],
                     cwd=str(PASTA_PROJETO), creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if servidor_no_ar():
            return True
        time.sleep(0.3)
    return False


def achar_janela(so_deste_processo=False):
    """A janela WinForms do app. FindWindow(título) não serve: o shell cria proxies de miniatura
    (Windows.Internal.Shell.TabProxyWindow) com o mesmo título."""
    import win32gui
    import win32process
    achadas = []

    def olhar(h, _):
        if (win32gui.GetWindowText(h) == TITULO and win32gui.GetClassName(h).startswith("WindowsForms10")
                and (not so_deste_processo or win32process.GetWindowThreadProcessId(h)[1] == os.getpid())):
            achadas.append(h)
        return True

    win32gui.EnumWindows(olhar, None)
    return achadas[0] if achadas else 0


def trazer_pra_frente():
    import win32con
    import win32gui
    hwnd = achar_janela()
    if not hwnd:
        return False
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    return True


def aplicar_icone():
    """O WinForms do pywebview usa o ícone do pythonw; troca pelo do app depois que a janela existe."""
    import win32con
    import win32gui
    for _ in range(100):
        hwnd = achar_janela(so_deste_processo=True)
        if hwnd:
            for tamanho, tipo in ((256, win32con.ICON_BIG), (16, win32con.ICON_SMALL)):
                ico = win32gui.LoadImage(0, str(ICONE), win32con.IMAGE_ICON, tamanho, tamanho, win32con.LR_LOADFROMFILE)
                win32gui.SendMessage(hwnd, win32con.WM_SETICON, tipo, ico)
            return
        time.sleep(0.1)


def main():
    import msvcrt
    os.makedirs(PASTA_ESTADO, exist_ok=True)
    trava = open(PASTA_ESTADO / "_janela.lock", "a+b")
    try:
        msvcrt.locking(trava.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        trazer_pra_frente()
        return 0

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    if not garantir_servidor():
        ctypes.windll.user32.MessageBoxW(0, "O Painel não conseguiu ligar o servidor local. Veja logs\\solicitacoes_nf.log.",
                                         TITULO, 0x10)
        return 1

    import webview
    webview.create_window(TITULO, f"http://127.0.0.1:{PORTA}/", width=1440, height=900, min_size=(1000, 640),
                          background_color="#0f2e2a", text_select=True)
    webview.start(aplicar_icone, gui="edgechromium", private_mode=False,
                  storage_path=str(PASTA_ESTADO / "app_webview"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
