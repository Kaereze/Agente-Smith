"""Arruma as fichas de design "Nielsen v*.html" de uma vez e manda para uma branch separada (nada entra na main).

    git pull --ff-only; python ferramentas/enviar_fichas_de_design.py

Na ordem: acha as fichas (na Área de Trabalho ou na pasta Designs) que o git ainda não publicou, tira da fila do git o que
estiver preparado, troca CPF/CNPJ válido por exemplo (mesma regra da trava de LGPD; nunca imprime o número), põe as fichas
na pasta Designs, faz o commit numa branch nova (o gancho roda os testes, ~1 min), envia a branch e volta para a main.
Se qualquer passo falhar, para ali, diz o motivo e deixa a main como estava. Só mexe em arquivos que batem com o padrão.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trocar_documento_por_exemplo as troca  # noqa: E402

PADRAO = "*Nielsen v*.html"
RAMO = "notas-design-fichas-v4-v5-limpas"
MENSAGEM = "Fichas de design v4 e v5 (20/11), numero de documento trocado por exemplo\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"


class Parar(Exception):
    pass


def git(raiz, *args, check=True):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise Parar(f"git {args[0]} falhou: {(r.stderr or r.stdout).strip()[-600:]}")
    return r


def pasta_designs(raiz):
    return next(iter(sorted(Path(raiz).glob("Segundo*/6 Documentos/Designs"))), None)


def achar_fichas(raiz, desktop, padrao):
    """Fichas que batem com o padrão e que o git ainda não publicou (não estão no último commit)."""
    achadas = []
    for base in (desktop, pasta_designs(raiz)):
        if base and Path(base).is_dir():
            achadas += sorted(Path(base).glob(padrao))
    pendentes = []
    for f in achadas:
        try:
            rel = f.resolve().relative_to(Path(raiz).resolve()).as_posix()
        except ValueError:
            pendentes.append(f)    # fora do projeto (Área de Trabalho): ainda não publicada
            continue
        if git(raiz, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode:
            pendentes.append(f)
    return pendentes


def enviar(raiz=RAIZ, desktop=None, padrao=PADRAO, ramo=RAMO, remoto="origin", dizer=print):
    desktop = Path(desktop) if desktop else Path.home() / "Desktop"
    if git(raiz, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        raise Parar("Volte para a main antes (git switch main).")
    fichas = achar_fichas(raiz, desktop, padrao)
    if not fichas:
        dizer("Nenhuma ficha para enviar (já publicadas ou não encontradas). Nada foi mexido.")
        return 0
    dizer(f"Achei {len(fichas)} ficha(s): " + ", ".join(f.name[:40] for f in fichas))

    nomes = [f.name for f in fichas]
    sujos = [linha for linha in git(raiz, "status", "--porcelain", "--untracked-files=no").stdout.splitlines()
             if not any(n in linha for n in nomes)]
    if sujos:
        raise Parar("Há outros arquivos alterados neste PC, então não mexi em nada: " + "; ".join(s[3:90] for s in sujos[:3]))

    for f in fichas:                      # tira da fila do git (se estiver preparada); não apaga nada
        try:
            rel = f.resolve().relative_to(Path(raiz).resolve()).as_posix()
            git(raiz, "restore", "--staged", "--", rel, check=False)
        except ValueError:
            pass

    for f in fichas:                      # troca o número por exemplo, no lugar onde a ficha está
        with open(f, encoding="utf-8", newline="") as a:
            novo, n = troca.trocar(a.read())
        with open(f, "w", encoding="utf-8", newline="") as a:
            a.write(novo)
        if troca.regra.novos(novo):
            raise Parar(f"{f.name[:40]}: sobrou número que não consegui trocar. Não enviei nada.")
        dizer(f"{f.name[:40]}: {n} número(s) trocados por exemplo")

    destino = pasta_designs(raiz)
    if destino is None:
        raise Parar("Não achei a pasta Designs do Segundo Cérebro.")
    caminhos = []
    for f in fichas:
        alvo = Path(destino) / f.name
        if f.resolve() != alvo.resolve():
            if alvo.exists():
                raise Parar(f"{f.name[:40]} já existe na pasta Designs. Não enviei nada.")
            shutil.move(str(f), str(alvo))
        caminhos.append(alvo.resolve().relative_to(Path(raiz).resolve()).as_posix())

    git(raiz, "switch", "-C", ramo)
    try:
        git(raiz, "add", "--", *caminhos)
        dizer("Fazendo o commit (o gancho roda os testes, cerca de 1 minuto)...")
        r = git(raiz, "commit", "-m", MENSAGEM, check=False)
        if r.returncode:
            raise Parar("O commit foi barrado: " + (r.stdout + r.stderr).strip()[-700:])
        dizer("Enviando para o GitHub (branch separada)...")
        git(raiz, "push", "-u", remoto, ramo)
    except Parar:
        git(raiz, "reset", "-q", check=False)
        git(raiz, "switch", "main", check=False)
        raise
    git(raiz, "switch", "main")
    dizer(f"PRONTO: as fichas foram para a branch {ramo} (a main não mudou). Este PC voltou para a main.")
    return 0


def main(argv=None, raiz=RAIZ, desktop=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--padrao", default=PADRAO)
    args = ap.parse_args(argv)
    try:
        return enviar(raiz=raiz, desktop=desktop, padrao=args.padrao)
    except Parar as e:
        print(f"PAREI: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
