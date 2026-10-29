"""Instalador do PC só com o Painel (29/10/2026): a configuração que ele grava e os arquivos do instalador."""
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def _modulo(nome):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "Automacoes" / f"{nome}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def projeto(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"dropbox_notas": {"ativo": True, "pastas": [str(tmp_path / "nao-existe")]},
                                                      "agentes": {"Clara": "x@y.com"}}), encoding="utf-8")
    return tmp_path


def test_grava_papel_operador_e_desliga_dropbox_que_nao_existe(projeto):
    r = _modulo("configurar_pc_so_painel").preparar("Ingrid", projeto)
    assert r == {"operador": "Ingrid", "papel": "so_painel", "dropbox": False}
    local = json.loads((projeto / "config.local.json").read_text(encoding="utf-8"))
    assert local["papel"] == "so_painel" and local["agentes"] == {"Ingrid": ""} and local["dropbox_notas"] == {"ativo": False}
    assert json.loads((projeto / "estado" / "app.json").read_text(encoding="utf-8"))["agente"] == "Ingrid"


def test_mantem_dropbox_ligado_quando_a_pasta_existe(projeto):
    pasta = projeto / "dropbox"
    pasta.mkdir()
    (projeto / "config.json").write_text(json.dumps({"dropbox_notas": {"ativo": True, "pastas": [str(pasta)]}}), encoding="utf-8")
    r = _modulo("configurar_pc_so_painel").preparar("Ingrid", projeto)
    assert r["dropbox"] is True
    assert "dropbox_notas" not in json.loads((projeto / "config.local.json").read_text(encoding="utf-8"))


def test_roda_de_novo_sem_perder_o_que_ja_existia(projeto):
    m = _modulo("configurar_pc_so_painel")
    (projeto / "config.local.json").write_text(json.dumps({"modo": "TESTE", "agentes": {"Outra": "a@b.com"}}), encoding="utf-8")
    (projeto / "estado").mkdir()
    (projeto / "estado" / "app.json").write_text(json.dumps({"tema": "dark", "agente": "Fulano"}), encoding="utf-8")
    m.preparar("Ingrid", projeto)
    m.preparar("Ingrid", projeto)
    local = json.loads((projeto / "config.local.json").read_text(encoding="utf-8"))
    assert local["modo"] == "TESTE" and set(local["agentes"]) == {"Outra", "Ingrid"}
    prefs = json.loads((projeto / "estado" / "app.json").read_text(encoding="utf-8"))
    assert prefs == {"tema": "dark", "agente": "Ingrid"}


def test_sem_nome_do_operador_nao_grava_nada(projeto):
    with pytest.raises(ValueError):
        _modulo("configurar_pc_so_painel").preparar("  ", projeto)
    assert not (projeto / "config.local.json").exists()


def test_o_papel_gravado_vira_pc_sem_outlook_pela_config_real(projeto, monkeypatch):
    import config
    _modulo("configurar_pc_so_painel").preparar("Ingrid", projeto)
    local = json.loads((projeto / "config.local.json").read_text(encoding="utf-8"))
    assert config.sem_outlook(local) and not config.e_principal(local)


def test_instalador_nao_leva_segredo_nenhum():
    for nome in ("Automacoes/instalar_pc_so_painel.ps1", "INSTALAR_PC_SO_PAINEL.bat", "Automacoes/testar_pc_novo.py",
                 "Automacoes/configurar_pc_so_painel.py", "Automacoes/gerar_segredo_rede.py"):
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        assert "BEGIN PRIVATE KEY" not in texto and "private_key\": \"" not in texto, nome
    ps1 = (RAIZ / "Automacoes" / "instalar_pc_so_painel.ps1").read_text(encoding="utf-8")
    assert ps1.isascii()                                   # PowerShell 5.1 lê arquivo sem BOM como ANSI: acento viraria lixo
    for etapa in ("Python", "Git", "Projeto", ".venv", "Chave do Google", "Configuracao", "WebView2", "Firewall", "Painel", "Teste final"):
        assert etapa in ps1, etapa
    assert "agendar_conferente" not in ps1 and "agendar_sincronizacao" not in ps1     # este PC não roda conferente nem cópia
