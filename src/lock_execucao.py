"""Trava entre processos: cópia, envio e conferência nunca rodam juntos."""
import datetime
import json
import msvcrt
import os

import pywintypes
import win32api
import win32con

from config import PASTA_ESTADO
from log_util import configurar_logging

logger = configurar_logging(__name__)

ARQUIVO_LOCK = str(PASTA_ESTADO / "_execucao.lock")
_ARQUIVO_MUTEX = ARQUIVO_LOCK + ".mutex"

IDADE_MAXIMA_SEGUNDOS = 60 * 60   # execução normal leva minutos; mais que isso = trava órfã


def _processo_esta_vivo(pid):
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        win32api.CloseHandle(handle)
        return True
    except pywintypes.error:
        return False


def _lock_esta_orfao(dados_lock):
    try:
        iniciado_em = datetime.datetime.fromisoformat(dados_lock["iniciado_em"])
        pid = dados_lock["pid"]
    except (KeyError, TypeError, ValueError):
        return True
    if (datetime.datetime.now() - iniciado_em).total_seconds() > IDADE_MAXIMA_SEGUNDOS:
        return True
    return not _processo_esta_vivo(pid)


def _dados_lock_atuais():
    return {"pid": os.getpid(), "iniciado_em": datetime.datetime.now().isoformat()}


def _criar_lock_atomicamente():
    try:
        descritor = os.open(ARQUIVO_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(descritor, json.dumps(_dados_lock_atuais()).encode("utf-8"))
    finally:
        os.close(descritor)
    return True


def adquirir_lock():
    os.makedirs(os.path.dirname(ARQUIVO_LOCK), exist_ok=True)
    with open(_ARQUIVO_MUTEX, "a+b") as arquivo_mutex:
        try:
            msvcrt.locking(arquivo_mutex.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            logger.warning("⚠️ Outra execução está começando exatamente agora — esta desiste.")
            return False
        try:
            return _decidir_e_adquirir_lock()
        finally:
            arquivo_mutex.seek(0)
            msvcrt.locking(arquivo_mutex.fileno(), msvcrt.LK_UNLCK, 1)


def _decidir_e_adquirir_lock():
    if _criar_lock_atomicamente():
        return True
    try:
        with open(ARQUIVO_LOCK, "r", encoding="utf-8") as f:
            dados_lock = json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Arquivo de trava ilegível ({e}) — tratando como abandonado.")
        dados_lock = {}

    if not _lock_esta_orfao(dados_lock):
        logger.warning(f"⚠️ Já existe uma execução rodando (PID {dados_lock.get('pid')}, "
                       f"iniciada {dados_lock.get('iniciado_em')}) — esta desiste pra não duplicar.")
        return False

    logger.warning(f"⚠️ Trava abandonada encontrada ({dados_lock}) — assumindo.")
    with open(ARQUIVO_LOCK, "w", encoding="utf-8") as f:
        json.dump(_dados_lock_atuais(), f)
    return True


def liberar_lock():
    """Só apaga se a trava for deste processo. Nunca levanta."""
    try:
        if not os.path.exists(ARQUIVO_LOCK):
            return
        with open(ARQUIVO_LOCK, "r", encoding="utf-8") as f:
            dados_lock = json.load(f)
        if dados_lock.get("pid") == os.getpid():
            os.remove(ARQUIVO_LOCK)
    except Exception as e:
        logger.warning(f"⚠️ Não consegui apagar a trava ({e}) — a próxima execução resolve sozinha.")
