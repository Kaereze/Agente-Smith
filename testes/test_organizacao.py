"""Organização do projeto (08/11/2026): cada pasta de src/ explica a si mesma, o mapa em linguagem simples cobre toda pasta da raiz e o
índice de módulos (gerado do código) está em dia."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
# pontos de entrada: os PCs, as tarefas do Windows e os instaladores os chamam por este caminho. Não mexa sem ajustar os 4 PCs.
ENTRADAS = {"app_servidor", "app_janela", "main", "conferente", "sincronizar", "confirmar_nfs", "conferir_copia", "identidade", "atualizador",
            "avisos_windows", "config", "ajustes"}


def test_so_ficam_em_src_os_pontos_de_entrada_e_cada_assunto_tem_pasta_com_explicacao():
    soltos = {f.stem for f in SRC.glob("*.py")}
    assert soltos == ENTRADAS, f"módulo solto em src/: {sorted(soltos - ENTRADAS)} · entrada que sumiu: {sorted(ENTRADAS - soltos)}"
    pastas = [p for p in SRC.iterdir() if p.is_dir() and p.name != "__pycache__"]
    assert len(pastas) >= 7
    for p in pastas:
        init = p / "__init__.py"
        assert init.exists(), f"{p.name}: falta o __init__.py"
        doc = ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))) or ""
        assert len(doc) > 80 and "Mexa aqui" in doc, f"{p.name}/__init__.py precisa explicar, em linguagem simples, quando mexer ali"


def _ignorada_pelo_git(pasta):
    """Pasta que só existe neste PC (o .gitignore a esconde): não faz parte do projeto, não precisa de explicação."""
    import subprocess
    try:
        return subprocess.run(["git", "check-ignore", "-q", pasta.name], cwd=RAIZ, capture_output=True).returncode == 0
    except OSError:
        return False


def test_comece_aqui_cita_toda_pasta_da_raiz_e_toda_pasta_de_src():
    texto = (RAIZ / "COMECE_AQUI.md").read_text(encoding="utf-8")
    ignoradas = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".gitattributes", "Segundo Cérebro"}
    for p in sorted(RAIZ.iterdir()):
        if p.is_dir() and p.name not in ignoradas and not _ignorada_pelo_git(p):
            assert f"`{p.name}/`" in texto or f"`{p.name}/` e" in texto or p.name.startswith(".") and f"`{p.name}/`" in texto, f"COMECE_AQUI.md não explica a pasta {p.name}/"
    for p in SRC.iterdir():
        if p.is_dir() and p.name != "__pycache__":
            assert f"`src/{p.name}/`" in texto, f"COMECE_AQUI.md não explica src/{p.name}/"


def test_indice_de_modulos_do_cofre_esta_em_dia():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mapa_dos_modulos", RAIZ / "ferramentas" / "mapa_dos_modulos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    atual = (RAIZ / "Segundo Cérebro (Agente Smith)" / "3 Mapa do projeto" / "Módulos por pasta.md").read_text(encoding="utf-8")
    assert atual.replace("\r\n", "\n") == mod.texto(), "rode: python ferramentas/mapa_dos_modulos.py"
