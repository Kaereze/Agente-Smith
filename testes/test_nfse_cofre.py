"""Certificado digital e saída dos testes de NFS-e nunca sobem pro GitHub (07/11/2026)."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))
import checar_commit  # noqa: E402


def test_commit_barra_certificado_pfx_e_p12():
    arquivos = {"nfse/BOA_VIAGEM.pfx": "x", "certificados/Hotel.P12": "x", "nfse/ok.py": "x = 1"}
    achados = checar_commit.problemas(list(arquivos), arquivos.get)
    assert any(a.startswith("nfse/BOA_VIAGEM.pfx") for a in achados)
    assert any(a.startswith("certificados/Hotel.P12") for a in achados)
    assert not any(a.startswith("nfse/ok.py") for a in achados)


def test_gitignore_cobre_certificado_e_saida_do_teste():
    linhas = {linha.strip() for linha in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()}
    for esperado in ("*.pfx", "*.p12", "saida_nfse_teste/", "nfse/dados_teste.json"):
        assert esperado in linhas, esperado


def test_nenhum_arquivo_do_pacote_tem_senha_escrita():
    """A senha só vem de variável de ambiente ou do teclado, nunca escrita no código."""
    for caminho in (RAIZ / "nfse").glob("*.py"):
        texto = caminho.read_text(encoding="utf-8")
        assert "senha=\"" not in texto.replace('senha=""', "") or caminho.name == "validacao.py", caminho.name
        assert "NFSE_CERT_SENHA" not in texto or caminho.name == "primeiro_teste.py", caminho.name
