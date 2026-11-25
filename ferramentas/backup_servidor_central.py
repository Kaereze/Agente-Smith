"""Cópia de segurança diária do banco do servidor central NESTE PC (o "Servidor RA"), sem Docker.

    pythonw ferramentas\\backup_servidor_central.py [--pasta C:\\ServidorCentral] [--dias 14]

É o que a tarefa agendada `ServidorCentral_Backup` roda (Automacoes\\agendar_backup_servidor_central.ps1), todo dia às 03:00.
Copia <pasta>\\central.sqlite para <pasta>\\copias\\central-AAAA-MM-DD.sqlite (cópia consistente com o servidor ligado: usa a
API de backup do SQLite) e apaga as com mais de 14 dias. Depois de copiar, ABRE a cópia e confere (integrity_check, número de
abas e de linhas). O resultado de cada rodada vai para <pasta>\\copias\\backup.log: só data, nome do arquivo, tamanho e
contagens, nunca dado de hóspede. Sai com erro (e escreve ERRO no log) se o banco não existe ou se a cópia não abre.
"""
import argparse
import datetime
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

PASTA_PADRAO = r"C:\ServidorCentral"


def conferir_copia(arquivo):
    """Abre a cópia e confere. -> (abas, linhas). RuntimeError se não estiver íntegra.
    Também deixa a cópia num arquivo só (journal_mode=DELETE): sem isto ela herda o modo WAL do banco e deixa -wal/-shm soltos."""
    con = sqlite3.connect(str(arquivo))
    try:
        con.execute("PRAGMA journal_mode=DELETE")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("a cópia não passou no integrity_check do SQLite")
        abas = con.execute("SELECT COUNT(*) FROM abas").fetchone()[0]
        linhas = con.execute("SELECT COUNT(*) FROM linhas").fetchone()[0]
        return abas, linhas
    finally:
        con.close()


def rodar(pasta, dias=14, hoje=None):
    """Faz e confere a cópia do dia. -> (arquivo da cópia, abas, linhas)."""
    from servidor_central.backup import fazer_backup
    pasta = Path(pasta)
    banco = pasta / "central.sqlite"
    if not banco.exists():   # sem isto o Armazem criaria um banco vazio e a cópia "daria certo" sem copiar nada
        raise FileNotFoundError(f"não achei o banco do servidor em {banco} (o servidor já rodou alguma vez?)")
    destino = fazer_backup(str(banco), pasta / "copias", hoje=hoje, dias=dias)
    abas, linhas = conferir_copia(destino)
    return destino, abas, linhas


def _anotar(pasta, texto):
    copias = Path(pasta) / "copias"
    copias.mkdir(parents=True, exist_ok=True)
    with open(copias / "backup.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", default=PASTA_PADRAO)
    ap.add_argument("--dias", type=int, default=14)
    args = ap.parse_args(argv)
    try:
        destino, abas, linhas = rodar(args.pasta, dias=args.dias)
    except Exception as e:   # o log é o único lugar onde quem olha vai ver (pythonw não tem janela)
        _anotar(args.pasta, f"ERRO {type(e).__name__}: {str(e)[:200]}")
        print(f"ERRO: {e}")
        return 1
    kb = Path(destino).stat().st_size // 1024
    texto = f"OK {Path(destino).name} {kb} KB, {abas} abas, {linhas} linhas"
    _anotar(args.pasta, texto)
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
