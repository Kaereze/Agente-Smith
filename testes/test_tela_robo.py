"""Tela do robô v3 (22/10/2026): a janela grande substitui a aba Robô e a tela de Log."""
import re
from pathlib import Path

import app_servidor

UI = Path(__file__).resolve().parent.parent / "app_ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
JS = (UI / "robo.js").read_text(encoding="utf-8")
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")


def test_robo_js_e_servido_e_carregado_depois_do_painel():
    assert app_servidor.ESTATICOS["/robo.js"][0] == "robo.js"
    assert HTML.index('<script src="/painel.js"></script>') < HTML.index('<script src="/robo.js"></script>')


def test_a_aba_antiga_e_a_tela_de_log_saem_do_caminho():
    assert 'id="v-robo"' not in HTML and "desenharRobo" not in HTML + PAINEL and "carregarRobo" not in HTML + PAINEL
    assert 'data-vista="robo"' not in HTML and "data-abrir-robo" in HTML
    assert 'if (v === "log") { if (typeof rbAbrir === "function") rbAbrir("reg"); return; }' in PAINEL   # quem pedia o Log abre a janela
    assert 'id="robo-dot"' not in HTML and 'id="robo" role="button"' in HTML                             # o chip substitui a bolinha


def test_janela_usa_a_peca_unica_e_fecha_com_esc():
    assert 'className = "modal-fundo rb-fundo"' in JS                    # mesma animação e foco das outras janelas
    assert re.search(r'class="rb-bt ic fant fechar" data-rb-fechar', JS)   # o Esc da peça única clica em .fechar
    assert "ev.stopImmediatePropagation()" in JS                         # Esc fecha primeiro a gaveta do pedido


def test_nada_de_glifo_solto_nem_botao_que_comanda_o_robo():
    assert "/api/enviar" in JS and "/api/comando" not in JS
    # Ligar/Pausar o robô (OK do João em 27/10/2026): só o usuário João vê (so-admin) e pausar pede confirmação
    assert "Pausar o envio automático" in JS and "Ligar o robô" in JS
    assert JS.count('so-admin" data-rb-liga') + JS.count('pri so-admin" data-rb-liga') >= 3
    assert "&#10003;" not in JS and "✓" not in JS.replace("// ", "")
