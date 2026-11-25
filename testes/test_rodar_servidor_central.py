"""ferramentas/rodar_servidor_central.py: o servidor roda como SISTEMA e precisa achar a chave do Google na pasta do usuário (--appdata)."""
import importlib.util
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("rodar_servidor_central", RAIZ / "ferramentas" / "rodar_servidor_central.py")
ferramenta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ferramenta)


def test_appdata_aponta_para_a_pasta_do_usuario_e_vazio_nao_mexe(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Windows\system32\config\systemprofile\AppData\Roaming")
    ferramenta.aplicar_appdata("")
    assert os.environ["APPDATA"].endswith("systemprofile\\AppData\\Roaming")   # sem argumento: não muda nada
    ferramenta.aplicar_appdata(r"C:\Users\fulano\AppData\Roaming")
    assert os.environ["APPDATA"] == r"C:\Users\fulano\AppData\Roaming"


def test_o_config_le_a_chave_pelo_appdata_do_usuario(monkeypatch):
    """O caminho da chave usa %APPDATA%: com --appdata a tarefa de SISTEMA acha a chave do usuário (e o token sai igual)."""
    import config
    monkeypatch.setenv("APPDATA", r"C:\Users\fulano\AppData\Roaming")
    cfg = {"caminho_chave_google": r"%APPDATA%\SolicitacoesNF\chave-api.json"}
    assert config.caminho_chave_google(cfg) == r"C:\Users\fulano\AppData\Roaming\SolicitacoesNF\chave-api.json"


def test_o_instalador_passa_o_appdata_e_usa_a_conta_sistema_sem_senha():
    texto = (RAIZ / "Automacoes" / "agendar_servidor_central.ps1").read_text(encoding="utf-8")
    backup = (RAIZ / "Automacoes" / "agendar_backup_servidor_central.ps1").read_text(encoding="utf-8")
    for t in (texto, backup):
        assert '-UserId "SYSTEM"' in t and "ServiceAccount" in t
        assert not re.search(r"-Password|ConvertTo-SecureString|-LogonType (Password|Interactive)", t)   # nada de senha guardada
        assert t.isascii()                                                                               # PowerShell 5.1 lê como ANSI
    assert "--appdata" in texto and "New-ScheduledTaskTrigger -AtStartup" in texto   # sobe ao ligar o Windows, sem ninguém entrar
