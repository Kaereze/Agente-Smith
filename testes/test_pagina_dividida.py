"""index.html dividido (07/11/2026): HTML, estilo.css e telas.js. O servidor entrega os três e o token continua só no HTML."""
from pathlib import Path

import app_servidor

UI = Path(__file__).resolve().parents[1] / "app_ui"


def test_index_html_ficou_pequeno_e_os_tres_arquivos_existem():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert html.count("\n") < 400 and "<style>" not in html
    assert '<link rel="stylesheet" href="/estilo.css">' in html and '<script src="/telas.js"></script>' in html
    assert (UI / "estilo.css").stat().st_size > 50_000 and (UI / "telas.js").stat().st_size > 30_000


def test_servidor_entrega_estilo_e_telas_e_o_token_fica_no_html():
    assert "/estilo.css" in app_servidor.ESTATICOS and "/telas.js" in app_servidor.ESTATICOS
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'const TOKEN = "__TOKEN__"' in html and "__TOKEN__" not in (UI / "telas.js").read_text(encoding="utf-8")


def test_so_ficam_inline_o_tema_o_token_e_o_guardiao_da_pagina_pela_metade():
    """O guardião precisa ficar no HTML: se um arquivo externo não vier, é ele que recarrega a página."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    inlines = __import__("re").findall(r"<script>([\s\S]*?)</script>", html)
    assert len(inlines) == 3 and "localStorage" in inlines[0] and "TOKEN" in inlines[1] and len(inlines[1]) < 400 and "__telaInteira" in inlines[2]
