"""Texto da página do Painel para os testes que conferem o código da tela: index.html + estilo.css + telas.js
from tela_texto import codigo_js
(o index.html foi dividido em 07/11/2026; quem confere regra de CSS ou de JavaScript lê os três juntos, nesta ordem)."""

def pagina(ui):
    """index.html + estilo.css + toda a lógica das telas (telas.js e as partes telas_*.js)."""
    return "".join([(ui / "index.html").read_text(encoding="utf-8"), (ui / "estilo.css").read_text(encoding="utf-8"), codigo_js(ui, "telas")])


def codigo_js(ui, base):
    """Um arquivo da tela dividido por assunto (painel.js, correio.js, telas.js): o principal e as partes `base_*.js`, na ordem de carga do index.html."""
    html = (ui / "index.html").read_text(encoding="utf-8")
    nomes = [n for n in __import__("re").findall(r'<script src="/([^"/]+\.js)"></script>', html) if n == f"{base}.js" or n.startswith(f"{base}_")]
    return "".join((ui / n).read_text(encoding="utf-8") for n in nomes)
