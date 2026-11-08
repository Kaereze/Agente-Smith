"""Pedido do titular (LGPD): onde os dados de uma pessoa estão neste PC, e tirar o que dá para tirar daqui.

    python ferramentas\pedido_titular.py localizar "123.456.789-09"
    python ferramentas\pedido_titular.py apagar-indice "maria@exemplo.com"
    python ferramentas\pedido_titular.py apagar-cache cache_textos_nf.json

Mostra só quantidades, nunca o conteúdo. Não apaga do Outlook, da planilha do hotel nem da Central (o hotel apaga a linha e a Central acompanha),
nem NF emitida (guarda fiscal de 5 anos). Passo a passo e prazo de 15 dias: Segundo Cérebro, "Dados de hóspedes (LGPD)". Anote o pedido
(data, hotel, o que foi feito) SEM copiar o CPF.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from privacidade import titular  # noqa: E402


def main(argv):
    if len(argv) < 3 or argv[1] not in ("localizar", "apagar-indice", "apagar-cache"):
        print(__doc__)
        return 2
    acao, alvo = argv[1], argv[2]
    if acao == "localizar":
        achados = titular.localizar(alvo)
        if not achados:
            print("Nada encontrado neste PC.")
        for arquivo, n in achados.items():
            print(f"  {arquivo}: {n}")
    elif acao == "apagar-indice":
        print(f"{titular.apagar_do_indice(alvo)} e-mail(s) tirado(s) do índice de pesquisa deste PC.")
    else:
        print("Apagado." if titular.apagar_arquivo(alvo) else "Esse arquivo não existe neste PC.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
