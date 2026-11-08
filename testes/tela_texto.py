"""Texto da página do Painel para os testes que conferem o código da tela: index.html + estilo.css + telas.js
(o index.html foi dividido em 07/11/2026; quem confere regra de CSS ou de JavaScript lê os três juntos, nesta ordem)."""

PARTES = ("index.html", "estilo.css", "telas.js")


def pagina(ui):
    return "".join((ui / n).read_text(encoding="utf-8") for n in PARTES if (ui / n).exists())
