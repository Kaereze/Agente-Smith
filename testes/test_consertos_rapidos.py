"""Consertos rápidos de design (24/10/2026): Enviar NF azul, formatos únicos, comparação em quantidade."""
import json
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parent.parent / "app_ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")


def test_enviar_nf_azul_no_topo_do_email():
    assert ".ol-resumo .rf-bts button.p{background:#479ef5!important" in HTML and "#2e7d57" not in HTML


def test_ficha_usa_os_formatos_unicos():
    assert "esc(fmtCarimbo(s))" in HTML and "fmtDoc(docTom)" in HTML and "fmtCep(cep)" in HTML and "fmtDoc(cpfTit)" in HTML


def test_visao_geral_compara_em_quantidade():
    assert "varPct" not in PAINEL and "varN(a.nfs, b.nfs, 1)" in PAINEL and "varN(a.recebidos.length, b.recebidos.length, 0)" in PAINEL


@pytest.mark.parametrize("entrada, saida", [
    ("12345678909", "123.456.789-09"), ("1234567890", "012.345.678-90"), ("123.456.789-09", "123.456.789-09"),
    ("12345678000195", "12.345.678/0001-95"), ("2345678000195", "02.345.678/0001-95"), ("passaporte X1", "passaporte X1"), ("", ""),
])
def test_fmt_doc(entrada, saida):
    ini = HTML.index("const digitosDe"); fim = HTML.index("function fmtCep")
    codigo = HTML[ini:fim] + f"process.stdout.write(fmtDoc({json.dumps(entrada)}));"
    assert subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8").stdout == saida


def test_fmt_cep_e_carimbo():
    ini = HTML.index("function horaDoCarimbo"); fim = HTML.index("function fmtCarimbo")
    fim = HTML.index("\n}", fim) + 2
    codigo = HTML[ini:fim] + """
      const r = [fmtCep("01001000"), fmtCep("01001-000"), fmtCep("123"),
                 fmtCarimbo({ data: "2026-10-23", carimbo: "10/23/2026 19:43:40" }), fmtCarimbo({ data: "2026-10-23", carimbo: "23/10/2026 9:05:00" })];
      process.stdout.write(JSON.stringify(r));"""
    r = json.loads(subprocess.run(["node", "-e", codigo], capture_output=True, text=True, encoding="utf-8").stdout)
    assert r == ["01001-000", "01001-000", "123", "23/10/2026 19:43", "23/10/2026 09:05"]
