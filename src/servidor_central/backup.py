"""Cópia de segurança diária do banco do servidor central: `python -m servidor_central.backup [pasta_das_copias]`.

Guarda uma cópia por dia (central-AAAA-MM-DD.sqlite) e apaga as com mais de 14 dias. Roda dentro do container
(`docker exec`), agendada no Windows do Servidor RA; a pasta de cópias fica fora do container (./dados/copias).
"""
import datetime
import os
import sys
from pathlib import Path

from servidor_central.armazem import Armazem

DIAS_GUARDADOS = 14


def fazer_backup(banco, pasta, hoje=None, dias=DIAS_GUARDADOS):
    hoje = hoje or datetime.date.today()
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"central-{hoje.isoformat()}.sqlite"
    armazem = Armazem(banco)
    try:
        armazem.copiar_para(str(destino))
    finally:
        armazem.fechar()
    for velho in pasta.glob("central-*.sqlite"):
        try:
            data = datetime.date.fromisoformat(velho.stem.removeprefix("central-"))
        except ValueError:
            continue
        if (hoje - data).days > dias:
            velho.unlink()
    return destino


def main():
    banco = os.environ.get("CENTRAL_BANCO", "central.sqlite")
    pasta = sys.argv[1] if len(sys.argv) > 1 else str(Path(banco).parent / "copias")
    print(f"Cópia feita: {fazer_backup(banco, pasta)}")


if __name__ == "__main__":
    main()
