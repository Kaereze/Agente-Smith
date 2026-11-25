"""Troca CPF/CNPJ válido (possível dado de hóspede) por um número de exemplo, nos arquivos indicados.

    python ferramentas/trocar_documento_por_exemplo.py ARQUIVO [ARQUIVO ...]            só diz quantos trocaria (não grava)
    python ferramentas/trocar_documento_por_exemplo.py ARQUIVO [ARQUIVO ...] --confirmo grava a troca

ARQUIVO pode ter curinga (ex.: "$HOME\\Desktop\\*Nielsen v*.html"). Usa a mesma regra da trava de LGPD
(testes/test_sem_documento_real.py): só troca número com dígitos verificadores válidos que não seja um dos exemplos nem
um dos já conhecidos. Mantém a pontuação (111.444.777-35 / 11.222.333/0001-81). NUNCA imprime o número: só quantidades,
para dar para rodar e colar o resultado no chat sem expor ninguém. Não mexe no resto do arquivo (nem nas quebras de linha).
"""
import argparse
import glob
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "testes"))
import test_sem_documento_real as regra  # noqa: E402  (uma só definição da regra: a da trava)

EXEMPLO_CPF = ("11144477735", "111.444.777-35")        # (sem pontuação, com pontuação)
EXEMPLO_CNPJ = ("11222333000181", "11.222.333/0001-81")


def trocar(texto):
    """-> (texto novo, quantos números foram trocados). Só mexe nos CPF/CNPJ válidos fora das listas da trava."""
    trocados = 0

    def troca(m):
        nonlocal trocados
        achado = m.group(0)
        digitos = re.sub(r"\D", "", achado)
        if digitos not in regra.novos(achado):
            return achado
        trocados += 1
        exemplo = EXEMPLO_CPF if len(digitos) == 11 else EXEMPLO_CNPJ
        return exemplo[1] if achado != digitos else exemplo[0]

    return regra.NUMERO.sub(troca, texto), trocados


def _arquivos(padroes):
    achados = []
    for p in padroes:
        achados += sorted(glob.glob(p)) if glob.has_magic(p) else [p]
    return achados


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="+")
    ap.add_argument("--confirmo", action="store_true", help="grava a troca (sem isto, só conta)")
    args = ap.parse_args(argv)
    arquivos = _arquivos(args.arquivos)
    if not arquivos:
        print("Nenhum arquivo encontrado.")
        return 1
    erro = False
    for arq in arquivos:
        nome = Path(arq).name
        try:
            with open(arq, encoding="utf-8", newline="") as f:   # newline="": mantém \r\n como está
                texto = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"{nome}: não consegui ler ({type(e).__name__})")
            erro = True
            continue
        novo, n = trocar(texto)
        if not n:
            print(f"{nome}: nenhum número para trocar")
            continue
        if not args.confirmo:
            print(f"{nome}: {n} número(s) seriam trocados por exemplo (repita com --confirmo para gravar)")
            continue
        with open(arq, "w", encoding="utf-8", newline="") as f:
            f.write(novo)
        sobrou = len(regra.novos(novo))
        print(f"{nome}: {n} número(s) trocados por exemplo; sobrou {sobrou}")
        erro = erro or bool(sobrou)
    return 1 if erro else 0


if __name__ == "__main__":
    sys.exit(main())
