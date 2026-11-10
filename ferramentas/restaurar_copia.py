"""Cópias de segurança dos dados deste PC (estado/copias): ver, conferir, fazer agora e restaurar.

    python ferramentas\restaurar_copia.py listar              as cópias que existem
    python ferramentas\restaurar_copia.py conferir            arquivos de dados que não abrem (JSON quebrado, SQLite com falha)
    python ferramentas\restaurar_copia.py agora               faz uma cópia agora
    python ferramentas\restaurar_copia.py restaurar [cópia] [arquivo ...]
                                                              volta a cópia (a mais nova se não disser qual) ou só os arquivos citados

Restaurar: feche o Painel antes. O que existia vira `*.antes-de-restaurar-<hora>`; nada é apagado.
Mostra só nomes e quantidades, nunca o conteúdo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sistema import armazem, copias  # noqa: E402


def main(argv):
    acao = argv[1] if len(argv) > 1 else ""
    if acao == "listar":
        zips = copias.listar()
        for z in zips:
            print(f"  {z.name}  {z.stat().st_size // 1024} KB")
        print(f"{len(zips)} cópia(s)." if zips else "Nenhuma cópia ainda.")
    elif acao == "conferir":
        ruins = copias.conferir()
        print("Todos os arquivos de dados abrem." if not ruins else "Não abrem: " + ", ".join(ruins))
        return 1 if ruins else 0
    elif acao == "agora":
        z = copias.fazer_copia()
        print(f"Cópia feita: {z.name}" if z else "Não havia nada para guardar.")
    elif acao == "restaurar":
        if armazem.caminho("_painel.lock").exists():
            print("O Painel parece aberto neste PC (existe a trava). Feche-o antes de restaurar.")
            return 2
        resto = argv[2:]
        zips = copias.listar()
        if resto and resto[0].endswith(".zip"):
            alvo = next((z for z in zips if z.name == resto[0]), None)
            resto = resto[1:]
        else:
            alvo = zips[0] if zips else None
        if not alvo:
            print("Cópia não encontrada. Use: listar")
            return 2
        try:
            voltaram = copias.restaurar(alvo, so=set(resto) or None)
        except ValueError as e:
            print(f"Não restaurei nada: {e}")
            return 1
        print(f"Restaurado de {alvo.name}: {len(voltaram)} arquivo(s).")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
