"""index.html dividido (07/11/2026): HTML, estilo.css e telas.js. O servidor entrega os três e o token continua só no HTML."""
from pathlib import Path

import app_servidor
from tela_texto import codigo_js

UI = Path(__file__).resolve().parents[1] / "app_ui"


def test_index_html_ficou_pequeno_e_os_tres_arquivos_existem():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert html.count("\n") < 400 and "<style>" not in html
    assert '<link rel="stylesheet" href="/estilo.css">' in html and '<script src="/telas.js"></script>' in html
    assert (UI / "estilo.css").stat().st_size > 50_000 and sum(f.stat().st_size for f in UI.glob("telas*.js")) > 30_000


def test_servidor_entrega_estilo_e_telas_e_o_token_fica_no_html():
    assert "/estilo.css" in app_servidor.ESTATICOS and "/telas.js" in app_servidor.ESTATICOS
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'const TOKEN = "__TOKEN__"' in html and "__TOKEN__" not in codigo_js(UI, "telas")


def test_so_ficam_inline_o_tema_o_token_e_o_guardiao_da_pagina_pela_metade():
    """O guardião precisa ficar no HTML: se um arquivo externo não vier, é ele que recarrega a página."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    inlines = __import__("re").findall(r"<script>([\s\S]*?)</script>", html)
    assert len(inlines) == 3 and "localStorage" in inlines[0] and "TOKEN" in inlines[1] and len(inlines[1]) < 400 and "__telaInteira" in inlines[2]


def test_cada_arquivo_js_da_tela_esta_no_html_uma_vez_e_o_servidor_entrega():
    """Arquivo da tela dividido por assunto (08/11/2026): nenhum .js solto, nenhum repetido, e todos servidos."""
    import re
    html = (UI / "index.html").read_text(encoding="utf-8")
    citados = re.findall(r'<script src="/([^"/]+\.js)"></script>', html)
    citados = [n for n in citados if n != "ajustes.js"]   # esse é gerado pelo servidor a partir do ajustes.json, não é arquivo da pasta
    em_disco = sorted(f.name for f in UI.glob("*.js"))
    assert sorted(citados) == em_disco, (set(em_disco) ^ set(citados))
    assert len(set(citados)) == len(citados)
    assert all(f"/{n}" in app_servidor.ESTATICOS for n in citados)
    # o principal de cada assunto vem antes das suas partes
    for base in ("telas", "correio", "painel"):
        ordem = [n for n in citados if n == f"{base}.js" or n.startswith(f"{base}_")]
        assert ordem[0] == f"{base}.js" and len(ordem) >= 4
