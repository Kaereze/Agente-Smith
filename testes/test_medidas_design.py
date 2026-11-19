"""Catraca do visual (19/11/2026, repaginação etapa 2): o CSS do Painel só pode ficar MAIS limpo, nunca mais sujo.
Cada teto abaixo é o valor medido em 19/11/2026. Quando uma etapa reduzir um número, ABAIXE o teto aqui (nunca suba).
Meta final de cada um em ferramentas/medir_design.py (METAS)."""
import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("medir_design", RAIZ / "ferramentas" / "medir_design.py")
medir_design = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(medir_design)

TETOS = {"tamanhos_de_texto": 25, "raios_de_canto": 20, "espacamentos_gap": 20, "cores_hex": 354, "importantes": 411, "camadas_z": 20}


def test_o_visual_nao_fica_mais_sujo_que_antes():
    medido = medir_design.medir()
    piores = {k: (medido[k], teto) for k, teto in TETOS.items() if medido[k] > teto}
    assert not piores, f"o CSS ganhou bagunça (medido, teto): {piores}. Use as variáveis de pecas/tokens.css em vez de valores novos."


def test_tokens_definem_a_regua_de_8_px_e_estao_carregados_na_tela():
    css = (RAIZ / "app_ui" / "pecas" / "tokens.css").read_text(encoding="utf-8")
    espacos = [int(v) for v in re.findall(r"--ds-s\d:\s*(\d+)px", css)]
    assert espacos == [4, 8, 12, 16, 24, 32, 48]
    assert len(re.findall(r"--ds-t\d+:", css)) == 7 and len(re.findall(r"--ds-r", css)) == 4
    assert "/pecas/tokens.css" in (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")


def test_trocar_de_operador_pergunta_antes_de_gravar():
    """19/11/2026: a troca de agente por um clique zerou a caixa do João duas vezes. A confirmação tem que vir ANTES do /api/agente."""
    js = (RAIZ / "app_ui" / "telas_janela.js").read_text(encoding="utf-8")
    assert js.index("confirmarTrocaDeOperador(nome)") < js.index('api("/api/agente"')
    assert 'getElementById("troca-nao")' in js or '$("troca-nao").focus()' in js   # o foco começa em Cancelar
