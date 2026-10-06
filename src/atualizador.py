"""Mantém o código de cada PC igual ao do GitHub (pedido do usuário, 06/10/2026: alterar num PC,
dar push, e os outros ficarem em sincronia).

O Painel de cada PC pergunta ao GitHub de tempos em tempos (e quando alguém aperta "Atualizar" na
página Atividade). Só atualiza quando dá pra ir pra frente sem conflito: nada alterado à mão neste
PC e nenhum commit local que o GitHub não tenha (o PC de quem programa nunca é atualizado por cima).
A atualização em si roda num PowerShell separado (Automacoes/atualizar_sozinho.ps1), porque ela
reinicia este próprio Painel.
"""
import subprocess
import sys
from pathlib import Path

from log_util import configurar_logging

logger = configurar_logging(__name__)

PASTA = Path(__file__).resolve().parent.parent
SCRIPT = PASTA / "Automacoes" / "atualizar_sozinho.ps1"
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git(*args, timeout=60):
    r = subprocess.run(["git", "-C", str(PASTA), *args], capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", creationflags=_SEM_JANELA)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:200] or f"git {args[0]} falhou")
    return r.stdout.strip()


def versao():
    """'abc1234 06/10' do código rodando neste PC ('?' sem git)."""
    try:
        return _git("log", "-1", "--format=%h %ad", "--date=format:%d/%m")
    except Exception:
        return "?"


def situacao():
    """-> {"atras": n, "frente": n, "limpo": bool, "erro": ""} em relação ao GitHub (faz git fetch)."""
    try:
        _git("fetch", "--quiet", "origin", timeout=120)
        ramo = _git("rev-parse", "--abbrev-ref", "HEAD")
        frente, atras = (int(x) for x in _git("rev-list", "--left-right", "--count", f"{ramo}...origin/{ramo}").split())
        limpo = not _git("status", "--porcelain", "--untracked-files=no")
        return {"atras": atras, "frente": frente, "limpo": limpo, "erro": ""}
    except Exception as e:
        return {"atras": 0, "frente": 0, "limpo": False, "erro": str(e)}


def pode_atualizar(s):
    return not s["erro"] and s["atras"] > 0 and s["frente"] == 0 and s["limpo"]


def motivo_para_nao(s):
    if s["erro"]:
        return f"não consegui falar com o GitHub ({s['erro'][:80]})"
    if s["atras"] == 0:
        return "já está na versão do GitHub"
    if s["frente"]:
        return f"este PC tem {s['frente']} commit(s) que o GitHub não tem — dê git push aqui"
    if not s["limpo"]:
        return "há arquivos alterados à mão neste PC (git status)"
    return ""


def atualizar():
    """Dispara o atualizar_sozinho.ps1 desligado deste processo (ele reinicia o Painel)."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | _SEM_JANELA
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
                     cwd=str(PASTA), creationflags=flags, close_fds=True)
    logger.info("🔄 Atualização disparada (git pull + reinício do conferente e do Painel).")


if __name__ == "__main__":
    s = situacao()
    print(versao(), s, motivo_para_nao(s) or "pode atualizar")
    sys.exit(0)
