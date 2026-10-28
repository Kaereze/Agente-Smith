"""Trava de colisão de classes CSS (27/10/2026).

O bloco "NF enviada" usava a classe `av` como estado "atenção", mas `.av` já é o círculo do avatar (32 x 32, display:grid):
o bloco encolhia para 32 px. Já tinha acontecido com o texto do reinício do Outlook. A regra: uma classe que é uma caixa
de tamanho fixo (regra solta com width e height) não pode ser usada como estado dentro de um `${...}` de class="...".
"""
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app_ui"


def caixas_de_tamanho_fixo(css):
    solta = {}
    for m in re.finditer(r"(?:^|\})\s*\.([A-Za-z][\w-]*)\s*\{([^}]*)\}", css):
        solta[m.group(1)] = solta.get(m.group(1), "") + m.group(2)
    return {c for c, corpo in solta.items()
            if re.search(r"(^|;)\s*width\s*:\s*\d", corpo) and re.search(r"(^|;)\s*height\s*:\s*\d", corpo)}


def estados_que_colidem(codigo, caixas):
    """[(classe, trecho)]: classe-caixa usada como texto entre aspas dentro de ${...} de um class="..."."""
    achados = []
    for m in re.finditer(r'class="((?:[^"$]|\$\{[^}]*\})*)"', codigo):
        for interp in re.findall(r"\$\{([^}]*)\}", m.group(1)):
            for a, b in re.findall(r'"([^"]*)"|\'([^\']*)\'', interp):
                achados += [(t, m.group(1)[:80]) for t in (a or b).split() if t in caixas]
    return achados


def test_detector_pega_o_erro_do_bloco_nf_enviada():
    css = ".av{width:32px;height:32px;display:grid}.cx-cobre{padding:12px}"
    caixas = caixas_de_tamanho_fixo(css)
    assert caixas == {"av"}
    assert estados_que_colidem('<section class="cx-cobre ${ok ? "ok" : "av"}">', caixas) == [("av", 'cx-cobre ${ok ? "ok" : "av"}')]
    assert estados_que_colidem('<section class="cx-cobre ${ok ? "cb-ok" : "cb-at"}">', caixas) == []


def test_nenhuma_classe_de_caixa_vira_estado_no_painel():
    css = (UI / "index.html").read_text(encoding="utf-8")
    for arq in UI.rglob("*.css"):
        css += arq.read_text(encoding="utf-8")
    caixas = caixas_de_tamanho_fixo(css)
    assert "av" in caixas   # o pé de apoio do teste: se sumir, a regra solta mudou de forma
    achados = []
    for arq in [UI / "index.html", *UI.rglob("*.js")]:
        achados += [(arq.name, *a) for a in estados_que_colidem(arq.read_text(encoding="utf-8"), caixas)]
    assert not achados, ("Classe de caixa de tamanho fixo usada como estado (renomeie o estado, ex. cb-at): "
                         + "; ".join(f"{a[0]}: {a[1]} em {a[2]}" for a in achados))
