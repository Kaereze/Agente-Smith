"""Ligar e pausar o robô pelo Painel (27/10/2026, só o João): escreve a caixa "Robô ligado?" da aba Status."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import app_servidor  # noqa: E402

ROBO = (RAIZ / "app_ui" / "robo.js").read_text(encoding="utf-8")
SERVIDOR = (RAIZ / "src" / "app_servidor.py").read_text(encoding="utf-8")


class _Backend:
    def __init__(self):
        self.escritas = []

    def escrever(self, planilha, itens):
        self.escritas.append((planilha, itens))


def _estado(demo=False, so_ver=False):
    e = app_servidor.Estado.__new__(app_servidor.Estado)
    e.backend, e.status, e.versao_tela, e.demo, e.so_ver = _Backend(), {}, 0, demo, so_ver
    e.cfg = {"planilha_central_id": "PLAN", "aba_status": "Status"}
    return e


def test_pausar_e_ligar_escrevem_a_caixa_do_robo_na_aba_status():
    e = _estado()
    assert e.definir_robo_ligado(False, "João") == {"ok": True, "ligado": False}
    assert e.backend.escritas[-1][1][0][1] == "FALSE" and e.backend.escritas[-1][1][0][0].endswith("!B1")
    assert e.resumo_status()["ligado"] is False
    e.definir_robo_ligado(True, "João")
    assert e.backend.escritas[-1][1][0][1] == "TRUE" and e.resumo_status()["ligado"] is True


def test_demo_e_so_leitura_nao_escrevem_na_planilha():
    assert _estado(demo=True).definir_robo_ligado(False, "João")["ok"] and not _estado(demo=True).backend.escritas
    e = _estado(so_ver=True)
    assert e.definir_robo_ligado(False, "João")["ok"] is False and not e.backend.escritas


def test_so_o_joao_liga_e_a_tela_pede_confirmacao_para_pausar():
    assert 'path == "/api/robo/ligado"' in SERVIDOR and "Só o João liga ou pausa o robô" in SERVIDOR
    assert 'data-rb-liga="0"' in ROBO and 'data-rb-liga="1"' in ROBO and "so-admin" in ROBO
    assert "Confirmar: pausar tudo" in ROBO and "rbz.confPausa" in ROBO
