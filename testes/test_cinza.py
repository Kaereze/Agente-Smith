"""Verdes antigos fora do modo cinza (usuário, 21/10/2026: "pode fazer tudo"). As cores de situação (etiquetas, ponto
de PC no ar, gráficos) e a tabela verde/creme do formulário ficam: não entram aqui."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HTML = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")


def test_a_tela_ja_nasce_no_cinza():
    assert '<div class="app modo-ol menu-fechado">' in HTML   # sem o instante da tela antiga verde ao abrir
    assert "html,body{background:#1f1f1f}" in HTML
    assert 'background_color="#1f1f1f"' in (RAIZ / "src" / "app_janela.py").read_text(encoding="utf-8")


def test_modo_cinza_sem_o_verde_escuro():
    regra = HTML.split(".app.modo-ol{")[1].split("}")[0]
    assert "#18402a" not in regra and "--borda-campo:#4a4a4a" in regra
    assert "#18402a" not in HTML.split("#v-correio.ol .tg.t-form{")[1].split("}")[0]
    assert '"#5f7a73"' not in HTML
