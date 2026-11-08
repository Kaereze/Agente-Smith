"""Gera o índice de módulos do Painel (Segundo Cérebro, "3 Mapa do projeto/Módulos por pasta.md") a partir do código.

    python ferramentas/mapa_dos_modulos.py

Uma página só diz em que pasta está cada módulo e para que serve (primeira linha do comentário de cada arquivo). Serve a quem não programa e
ao Claude: ler esta página custa menos do que procurar arquivo por arquivo. O texto nunca fica velho: sai do código, e um teste
(testes/test_organizacao.py) falha se o documento ficar para trás.
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
DESTINO = RAIZ / "Segundo Cérebro (Agente Smith)" / "3 Mapa do projeto" / "Módulos por pasta.md"


def _linha1(arquivo):
    try:
        doc = ast.get_docstring(ast.parse(arquivo.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        doc = ""
    return doc.strip().split("\n")[0].replace("|", "/")[:150]


def texto():
    L = ["---", "tipo: mapa", 'pasta: "3 Mapa do projeto"', 'pai: "[[00 Início]]"', "tags: [cerebro/mapa]", "---", "# Módulos por pasta", "",
         "> Gerado por `ferramentas/mapa_dos_modulos.py` a partir do código. **Não edite à mão.** Mapa das pastas em linguagem simples: `COMECE_AQUI.md` (raiz do projeto).", "",
         "## Programas que os PCs abrem pelo nome (ficam em `src/`)", "", "| Arquivo | Para que serve |", "|---|---|"]
    for f in sorted(SRC.glob("*.py")):
        L.append(f"| `src/{f.name}` | {_linha1(f)} |")
    for pasta in sorted(p for p in SRC.iterdir() if p.is_dir() and (p / "__init__.py").exists()):
        doc = ast.get_docstring(ast.parse((pasta / "__init__.py").read_text(encoding="utf-8"))) or ""
        L += ["", f"## `src/{pasta.name}/`: {doc.split(chr(10))[0].rstrip('.')}", ""]
        resto = [l for l in doc.split("\n")[1:] if l.strip() and not l.startswith("Mapa de todas")]
        L += [*resto[:1], "", "| Módulo | Para que serve |", "|---|---|"]
        for f in sorted(pasta.glob("*.py")):
            if f.stem != "__init__":
                L.append(f"| `{f.stem}` | {_linha1(f)} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    DESTINO.write_text(texto(), encoding="utf-8")
    print("escrito:", DESTINO.name)
