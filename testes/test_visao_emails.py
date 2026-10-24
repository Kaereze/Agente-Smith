"""Visão geral abria com "E-mails na caixa: 0" (23/10/2026): desenhava antes de os e-mails chegarem e não redesenhava."""
from pathlib import Path

CORREIO = (Path(__file__).resolve().parent.parent / "app_ui" / "correio.js").read_text(encoding="utf-8")


def test_emails_chegando_redesenham_a_visao_geral():
    corpo = CORREIO[CORREIO.index("async function carregarCorreio"):CORREIO.index("const doEscopo")]
    assert 'pn.vista === "visao"' in corpo and "desenharVisao()" in corpo
