"""Aba Robô e usuário João só no PC dele (22/10/2026)."""
import app_servidor

CFG = {"agentes": {"João": {}, "Cristian": {}, "Clara": {}, "Bernardo": {}, "_nota": {}}, "painel": {}}


def _papel(monkeypatch, principal):
    monkeypatch.setattr(app_servidor, "e_principal", lambda cfg: principal)


def test_joao_so_aparece_e_so_vale_no_pc_dele(monkeypatch):
    _papel(monkeypatch, True)
    assert app_servidor.operadores_deste_pc(CFG) == ["João", "Cristian", "Clara", "Bernardo"]
    assert app_servidor.e_admin_aqui(CFG, "João") and not app_servidor.e_admin_aqui(CFG, "Clara")
    _papel(monkeypatch, False)
    assert app_servidor.operadores_deste_pc(CFG) == ["Cristian", "Clara", "Bernardo"]   # João some dos outros PCs
    assert not app_servidor.e_admin_aqui(CFG, "João")                                    # e a opção de admin também
    assert app_servidor.e_admin_aqui(CFG, "João", liberado=True)                         # modo casa / demonstração


def test_admins_vem_da_configuracao(monkeypatch):
    _papel(monkeypatch, True)
    cfg = {**CFG, "painel": {"admins": ["João", "Clara"]}}
    assert app_servidor.e_admin_aqui(cfg, "Clara")
    _papel(monkeypatch, False)
    assert app_servidor.operadores_deste_pc(cfg) == ["Cristian", "Bernardo"]


def test_pc_extra_do_admin_ganha_as_abas_sem_virar_principal(monkeypatch):
    """PC de casa do João (20/11/2026): vê Monitoramento/Agentes, mas só ele, e só no PC listado em painel.pcs_admin."""
    _papel(monkeypatch, False)
    monkeypatch.setattr(app_servidor.socket, "gethostname", lambda: "desktop-7j2e10s")   # maiúscula/minúscula não importa
    cfg = {**CFG, "painel": {"pcs_admin": ["DESKTOP-7J2E10S"]}}
    assert app_servidor.e_admin_aqui(cfg, "João") and not app_servidor.e_admin_aqui(cfg, "Clara")
    assert app_servidor.operadores_deste_pc(cfg) == ["João", "Cristian", "Clara", "Bernardo"]
    assert not app_servidor.e_principal(cfg)   # continua sem copiar nem enviar: papel principal é outra coisa
    monkeypatch.setattr(app_servidor.socket, "gethostname", lambda: "DESKTOP-OUTRO")
    assert not app_servidor.e_admin_aqui(cfg, "João") and app_servidor.operadores_deste_pc(cfg) == ["Cristian", "Clara", "Bernardo"]
