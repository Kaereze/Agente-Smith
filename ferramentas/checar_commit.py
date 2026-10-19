"""Checagem antes de cada commit (hook pre-commit em .githooks/, skill setup-pre-commit adaptada para Python).

1. Nenhum arquivo do robô que nunca sobe (estado/, logs/, saida_simulacao/, config.local.json) nem com nome de
   credencial (chave*.json, conta de serviço, .pem, .key, .env).
2. Nenhum conteúdo com cara de credencial no que vai ser commitado. O valor nunca aparece, só o arquivo e o tipo.
3. Todos os testes passando.

Ligar neste PC (uma vez):  git config core.hooksPath .githooks
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "testes"))
from test_segredos import NOMES_PROIBIDOS, PADROES  # noqa: E402  (mesmos padrões da trava dos testes)

PASTAS_PROIBIDAS = ("estado/", "logs/", "saida_simulacao/")
ARQUIVOS_PROIBIDOS = ("config.local.json", "FALHA_CRITICA.txt")


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, check=True).stdout


def arquivos_no_commit():
    saida = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in saida.decode("utf-8").split("\0") if p]


def problemas(arquivos, ler):
    achados = []
    for rel in arquivos:
        if rel.startswith(PASTAS_PROIBIDAS) or rel.rsplit("/", 1)[-1] in ARQUIVOS_PROIBIDOS:
            achados.append(f"{rel} (dado do robô, nunca sobe)")
            continue
        if NOMES_PROIBIDOS.search(rel):
            achados.append(f"{rel} (nome de credencial)")
            continue
        texto = ler(rel)
        achados += [f"{rel} ({tipo})" for tipo, padrao in PADROES.items() if padrao.search(texto)]
    return achados


def _ler_do_indice(rel):
    try:
        dados = _git("show", f":{rel}")
    except subprocess.CalledProcessError:
        return ""
    return "" if len(dados) > 5_000_000 else dados.decode("utf-8", errors="ignore")


def main():
    sys.stderr.reconfigure(encoding="utf-8")
    achados = problemas(arquivos_no_commit(), _ler_do_indice)
    if achados:
        print("COMMIT BARRADO: isto não pode ir pro GitHub:", *achados, sep="\n  - ", file=sys.stderr)
        print("Tire do commit com:  git restore --staged <arquivo>", file=sys.stderr)
        return 1
    testes = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=RAIZ)
    if testes.returncode:
        print("COMMIT BARRADO: há testes falhando (veja acima).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
