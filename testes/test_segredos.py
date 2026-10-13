"""Trava contra vazamento (usuário, 13/10/2026: "guarde credenciais e não deixe elas serem vazadas de jeito nenhum").

Roda com os outros testes antes de cada entrega: se algum arquivo que vai pro GitHub tiver cara de credencial
(chave privada, chave de conta de serviço do Google, token do GitHub, chave de API do Google), o teste falha
e nada é enviado. O valor nunca aparece na mensagem de erro, só o arquivo e o tipo.
"""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADROES = {
    "chave privada": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "chave de conta de serviço do Google": re.compile(r'"private_key"\s*:\s*"-----BEGIN'),
    "token do GitHub": re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
    "chave de API do Google": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}
NOMES_PROIBIDOS = re.compile(r"(?:^|/)(?:chave[^/]*\.json|[^/]*service[-_]?account[^/]*\.json|[^/]*\.pem|[^/]*\.key|\.env)$",
                             re.IGNORECASE)


def _arquivos_do_repositorio():
    saida = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=RAIZ,
                           capture_output=True, check=True).stdout
    return [p for p in saida.decode("utf-8").split("\0") if p]


def test_nenhum_arquivo_com_nome_de_credencial():
    proibidos = [p for p in _arquivos_do_repositorio() if NOMES_PROIBIDOS.search(p)]
    assert not proibidos, f"arquivo com nome de credencial indo pro GitHub: {proibidos}"


def test_nenhum_conteudo_com_cara_de_credencial():
    achados = []
    for rel in _arquivos_do_repositorio():
        caminho = RAIZ / rel
        if not caminho.is_file() or caminho.stat().st_size > 5_000_000:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        achados += [f"{rel} ({tipo})" for tipo, padrao in PADROES.items() if padrao.search(texto)]
    assert not achados, f"possível credencial no repositório: {achados}"
