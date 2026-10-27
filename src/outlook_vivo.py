"""Guardião do Outlook (usuário, 13/10/2026: "deixa o Outlook obrigatoriamente aberto enquanto o PC estiver ativo").

Por quê: em 10/10 o Outlook do PC do Cristian fechou e, no dia seguinte, o robô (pelo COM) abriu um Outlook ESCONDIDO
("-Embedding", sem janela). As contas são POP3 e Outlook sem janela não faz Enviar/Receber: nada chegou na caixa por
3 dias, e o Painel ainda dizia "Outlook aberto" (só olhava se o OUTLOOK.EXE existia).

- estado(): "aberto" (tem a janela principal, mesmo minimizada ou escondida na bandeja), "sem_janela" (só aberto pelo
  COM, não recebe e-mail) ou "fechado". None se não deu pra saber.
- garantir(): se não está "aberto", abre o Outlook normal (igual a clicar no ícone) e espera a janela aparecer.
- iniciar_guardiao(): fio que confere a cada 60 s enquanto o PC estiver ligado (roda dentro do conferente).
Regra: o robô não chama o Outlook pelo COM sem antes passar por garantir() (senão nasce outro Outlook escondido).
"""
import os
import subprocess
import threading
import time

from log_util import configurar_logging

logger = configurar_logging("outlook_vivo")

ABERTO, SEM_JANELA, FECHADO = "aberto", "sem_janela", "fechado"
INTERVALO_SEGUNDOS = 60
ESPERA_ABRIR_SEGUNDOS = 90
PAUSA_DEPOIS_DE_FALHAS_SEGUNDOS = 30 * 60   # 3 tentativas sem janela: para de insistir por 30 min (não fica em laço)
CLASSE_JANELA_OUTLOOK = "rctrl_renwnd32"     # janela principal do Outlook clássico
_SEM_JANELA_PRETA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
REINICIO_TEMPO_REDE = 240   # o PC de outro agente demora: fecha, abre, espera as contas e manda o que estava preso
_reinicio = threading.Lock()
_cache = {"em": -1e9, "estado": None}
_falhas = {"n": 0, "pausa_ate": 0.0}


def _em_teste():
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _pids_outlook():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/FO", "CSV", "/NH"], capture_output=True,
                       text=True, timeout=15, creationflags=_SEM_JANELA_PRETA)
    pids = set()
    for linha in (r.stdout or "").splitlines():
        partes = [p.strip('"') for p in linha.split('","')]
        if len(partes) > 1 and partes[0].lower().startswith("outlook.exe") and partes[1].strip('"').isdigit():
            pids.add(int(partes[1].strip('"')))
    return pids


def _pids_com_janela(pids):
    """Dos processos, quais têm a janela principal do Outlook (visível ou não: escondido na bandeja conta como aberto)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    achados = set()
    tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cada(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            nome = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, nome, 64)
            if nome.value == CLASSE_JANELA_OUTLOOK:
                achados.add(pid.value)
        return True

    user32.EnumWindows(tipo(cada), 0)
    return achados


def estado(cache_segundos=20):
    """'aberto' | 'sem_janela' | 'fechado' | None."""
    if time.monotonic() - _cache["em"] < cache_segundos and _cache["estado"] is not None:
        return _cache["estado"]
    try:
        pids = _pids_outlook()
        atual = FECHADO if not pids else (ABERTO if _pids_com_janela(pids) else SEM_JANELA)
    except Exception:
        logger.debug("estado do Outlook", exc_info=True)
        return None
    _cache.update(em=time.monotonic(), estado=atual)
    return atual


def _abrir():
    """Abre o Outlook como se fosse pelo ícone (o Windows acha o outlook.exe pelo registro "App Paths")."""
    os.startfile("outlook.exe")


def _fechar_escondido():
    """Fecha o Outlook que está sem janela (aberto só pelo COM) pra abrir de novo do jeito certo."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        win32com.client.GetActiveObject("Outlook.Application").Quit()
    except Exception:
        logger.debug("fechar Outlook escondido", exc_info=True)


def _esperar_aberto(segundos):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if estado(cache_segundos=0) == ABERTO:
            return True
        time.sleep(3)
    return False


def garantir(motivo=""):
    """Deixa o Outlook aberto COM janela. -> True se está pronto pra o robô usar."""
    if _em_teste():
        return True
    atual = estado(cache_segundos=0)
    if atual in (ABERTO, None):
        _falhas["n"] = 0
        return atual == ABERTO or atual is None
    if time.monotonic() < _falhas["pausa_ate"]:
        return False
    quando = f" ({motivo})" if motivo else ""
    logger.warning(f"⚠️ Outlook {'sem janela (não recebe e-mail)' if atual == SEM_JANELA else 'fechado'}{quando}: abrindo o Outlook normal")
    try:
        _abrir()
        if _esperar_aberto(ESPERA_ABRIR_SEGUNDOS // 2):
            logger.info("✅ Outlook aberto com janela: Enviar/Receber volta a funcionar")
            _falhas["n"] = 0
            return True
        if estado(cache_segundos=0) == SEM_JANELA:   # o processo escondido não ganhou janela: fecha e abre de novo
            logger.warning("⚠️ O Outlook escondido não ganhou janela: fechando e abrindo de novo")
            _fechar_escondido()
            time.sleep(10)
            _abrir()
        if _esperar_aberto(ESPERA_ABRIR_SEGUNDOS):
            logger.info("✅ Outlook aberto com janela: Enviar/Receber volta a funcionar")
            _falhas["n"] = 0
            return True
    except Exception as e:
        logger.warning(f"⚠️ Não consegui abrir o Outlook ({e})")
    _falhas["n"] += 1
    if _falhas["n"] >= 3:
        _falhas.update(n=0, pausa_ate=time.monotonic() + PAUSA_DEPOIS_DE_FALHAS_SEGUNDOS)
        logger.error("❌ Outlook não abriu com janela em 3 tentativas: paro de insistir por 30 min (veja o PC)")
    return False


def iniciar_guardiao(intervalo=INTERVALO_SEGUNDOS):
    """Fio que mantém o Outlook aberto enquanto este processo (o conferente, ligado com o Windows) estiver rodando."""
    def rodar():
        while True:
            try:
                garantir("guardião")
            except Exception:
                logger.debug("guardião do Outlook", exc_info=True)
            time.sleep(intervalo)

    threading.Thread(target=rodar, name="guardiao_outlook", daemon=True).start()
    logger.info(f"🛡️ Guardião do Outlook ligado: confere a cada {intervalo}s e abre o Outlook se fechar ou ficar sem janela")


def aplicativo(motivo=""):
    """Porta única do robô pro Outlook: garante a janela antes e só então conecta pelo COM.
    Se o Outlook não abrir com janela, avisa em vez de criar um Outlook escondido."""
    if not garantir(motivo):
        raise RuntimeError("Outlook fechado ou sem janela neste PC (o guardião está tentando abrir)")
    import win32com.client
    return win32com.client.Dispatch("Outlook.Application")


def pode_usar():
    """Pro Painel: só mexe no Outlook pelo COM se ele já está aberto com janela (nunca cria um escondido)."""
    return _em_teste() or estado() == ABERTO


def reiniciar():
    """Fecha o Outlook à força e abre de novo, o que o João fazia à mão (27/10/2026, botão "caixas com problema"), e
    deixa mandar o que estava preso. -> {"ok", "segundos", "saiu", "presos"} | {"erro": texto}.
    Quem chama já confirmou na tela; e-mail aberto sendo escrito o Outlook costuma guardar como rascunho."""
    if _em_teste():
        return {"ok": True, "segundos": 0, "saiu": 0, "presos": 0}
    if not _reinicio.acquire(blocking=False):
        return {"erro": "o Outlook deste PC já está sendo reiniciado"}
    inicio = time.monotonic()
    try:
        logger.warning("🔁 Reiniciando o Outlook à força (pedido pelo Painel)")
        subprocess.run(["taskkill", "/F", "/IM", "OUTLOOK.EXE"], capture_output=True, timeout=30, creationflags=_SEM_JANELA_PRETA)
        fim = time.monotonic() + 20
        while time.monotonic() < fim and _pids_outlook():
            time.sleep(1)
        _cache.update(em=-1e9, estado=None)
        _falhas.update(n=0, pausa_ate=0.0)
        time.sleep(2)
        if not garantir("reinício pedido pelo Painel"):
            return {"erro": "o Outlook não abriu de novo: abra pelo ícone no PC"}
        time.sleep(8)   # as contas POP3 carregam depois da janela
        import enviar_receber
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        r = enviar_receber.rodar_aqui(win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI"), max_seg=40)
        if r.get("erro"):
            return {"ok": True, "segundos": round(time.monotonic() - inicio, 1), "saiu": 0, "presos": None, "aviso": r["erro"]}
        return {"ok": True, "segundos": round(time.monotonic() - inicio, 1), "saiu": r.get("saiu", 0), "presos": r.get("presos", 0)}
    except Exception as e:
        logger.warning(f"⚠️ Reinício do Outlook falhou: {e}")
        return {"erro": f"não deu certo ({str(e)[:80]})"}
    finally:
        _reinicio.release()
