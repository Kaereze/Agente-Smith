"""Mantém o código de cada PC igual ao do GitHub (pedido do usuário, 06/10/2026: alterar num PC,
dar push, e os outros ficarem em sincronia).

O Painel de cada PC pergunta ao GitHub de tempos em tempos (e quando alguém aperta "Atualizar" na
página Atividade). Só atualiza quando dá pra ir pra frente sem conflito: nada alterado à mão neste
PC e nenhum commit local que o GitHub não tenha (o PC de quem programa nunca é atualizado por cima).
O git pull e as bibliotecas rodam aqui, esperando o resultado (o erro, se houver, volta pra quem
pediu e aparece na página Atividade). O reinício (Automacoes/reiniciar_servicos.ps1) derruba este próprio
Painel, então roda FORA dele: pela tarefa SolicitacoesNF_Reiniciar do Agendador do Windows.

11/10/2026: lançado de dentro do Painel (que roda numa tarefa agendada) o PowerShell solto não subia — os 3 PCs
baixaram o código novo e ficaram com o velho na memória, e o log dizia "reiniciando" sem conferir. Agora o pedido
vai pro Agendador, o script registra começo e fim em logs/atualizacao.log e o Painel avisa se não reiniciou.
"""
import subprocess
import sys
from pathlib import Path

from log_util import configurar_logging

logger = configurar_logging(__name__)

PASTA = Path(__file__).resolve().parent.parent
SCRIPT_REINICIO = PASTA / "Automacoes" / "reiniciar_servicos.ps1"
_SAIR_DO_JOB = 0x01000000   # CREATE_BREAKAWAY_FROM_JOB: a tarefa agendada não leva o script junto ao cair
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TAREFA_REINICIO = "SolicitacoesNF_Reiniciar"


def pedir_reinicio():
    """Cria (ou refaz) a tarefa SolicitacoesNF_Reiniciar só deste usuário — sem administrador, igual às outras
    tarefas do projeto — e manda o Agendador rodar agora. -> texto pro log | exceção se o Agendador recusar."""
    script = str(SCRIPT_REINICIO).replace("'", "''")
    pasta = str(PASTA).replace("'", "''")
    ps = ("$ErrorActionPreference = 'Stop'; "
          f"$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{script}\"' -WorkingDirectory '{pasta}'; "
          "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5); "
          "$p = New-ScheduledTaskPrincipal -UserId \"$env:USERDOMAIN\\$env:USERNAME\" -LogonType Interactive -RunLevel Limited; "
          f"Register-ScheduledTask -TaskName '{TAREFA_REINICIO}' -Action $a -Settings $s -Principal $p -Force | Out-Null; "
          f"Start-ScheduledTask -TaskName '{TAREFA_REINICIO}'")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], capture_output=True,
                       text=True, timeout=90, encoding="utf-8", errors="replace", creationflags=_SEM_JANELA)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300] or "o Agendador recusou")
    return "reinício pedido ao Agendador do Windows"


def _reinicio_solto():
    """Jeito antigo (PowerShell solto), só se o Agendador recusar."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | _SEM_JANELA
    comando = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT_REINICIO)]
    try:
        subprocess.Popen(comando, cwd=str(PASTA), creationflags=flags | _SAIR_DO_JOB, close_fds=True)
    except OSError:
        subprocess.Popen(comando, cwd=str(PASTA), creationflags=flags, close_fds=True)
    return "reinício disparado (PowerShell solto)"


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
    """git pull só pra frente + bibliotecas, e reinício dos serviços. -> (ok, texto pra quem pediu)"""
    antes = versao()
    try:
        _git("pull", "--ff-only", timeout=300)
    except Exception as e:
        logger.warning(f"⚠️ git pull falhou: {e}")
        return False, f"git pull falhou: {e}"
    python = PASTA / ".venv" / "Scripts" / "python.exe"
    try:
        subprocess.run([str(python), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r",
                        str(PASTA / "requirements.txt")], cwd=str(PASTA), timeout=600, capture_output=True,
                       creationflags=_SEM_JANELA)
    except Exception as e:
        logger.warning(f"⚠️ pip install falhou ({e}) — sigo com as bibliotecas que já estão aí")
    try:
        como = pedir_reinicio()
    except Exception as e:
        logger.warning(f"⚠️ O Agendador do Windows não aceitou o reinício ({e}) — tentando o PowerShell solto")
        como = _reinicio_solto()
    # não diz "reiniciado": quem confirma é o script (logs/atualizacao.log) e o Painel novo ao subir
    logger.info(f"🔄 Atualizado de {antes} para {versao()} — {como} (confirmação em logs/atualizacao.log).")
    return True, f"atualizado de {antes} para {versao()}; {como}"


if __name__ == "__main__":
    s = situacao()
    print(versao(), s, motivo_para_nao(s) or "pode atualizar")
    sys.exit(0)
