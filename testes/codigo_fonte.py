"""Ler o código-fonte do Painel nos testes sem depender de em qual pasta de src/ cada módulo mora (src foi dividida em pastas por assunto em 08/11/2026)."""
from pathlib import Path


def achar(raiz, nome):
    """Caminho do módulo pelo nome (ex.: "envio_nf"), esteja ele em src/ ou numa das pastas de assunto."""
    achados = sorted((Path(raiz) / "src").rglob(f"{nome}.py"))
    assert len(achados) == 1, f"módulo '{nome}': {len(achados)} arquivos achados em src/"
    return achados[0]


def fonte(raiz, nome):
    return achar(raiz, nome).read_text(encoding="utf-8")


def fonte_servidor(raiz):
    """O servidor inteiro: app_servidor + a tabela de rotas + as quatro partes do Estado."""
    src = Path(raiz) / "src"
    return "".join(p.read_text(encoding="utf-8") for p in [src / "app_servidor.py", src / "painel" / "rotas_api.py", *sorted((src / "painel").glob("estado_*.py"))])


def modulos(raiz):
    """Nome de todos os módulos de src/ (qualquer pasta), sem os __init__."""
    return sorted(p.stem for p in (Path(raiz) / "src").rglob("*.py") if p.stem != "__init__")
