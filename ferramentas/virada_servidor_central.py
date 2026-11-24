"""Manda ligar ou desligar o servidor central nos PCs, pelo canal Comandos_PC (que fica no Google de propósito) — etapa 5.

    python ferramentas/virada_servidor_central.py --ligar http://IP:8770 --para TODOS --confirmo
    python ferramentas/virada_servidor_central.py --desligar --para TODOS --confirmo
    python ferramentas/virada_servidor_central.py --ver                  mostra as respostas dos PCs (sem dado de hóspede)
    python ferramentas/virada_servidor_central.py --onde http://IP:8770  mostra QUEM está no servidor e quem ainda está no Google

Cada PC confere o servidor antes de ligar e responde o motivo se não ligou. Roteiro completo, com horário, cópia final e volta:
Segundo Cérebro/6 Documentos/Plano da API central.md (seção "Virada").
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    quem = ap.add_mutually_exclusive_group(required=True)
    quem.add_argument("--ligar", metavar="URL", help="endereço do servidor, ex.: http://10.145.150.247:8770")
    quem.add_argument("--desligar", action="store_true")
    quem.add_argument("--ver", action="store_true")
    quem.add_argument("--onde", metavar="URL", help="endereço do servidor: diz quem está nele e quem ainda está no Google")
    ap.add_argument("--para", default="TODOS", help="nome do PC (ex.: DESKTOP-7M6539V) ou TODOS")
    ap.add_argument("--confirmo", action="store_true", help="exigido para ligar ou desligar")
    args = ap.parse_args(argv)

    from config import carregar_config, caminho_chave_google
    from central.sheets import BackendGoogle
    from central import virada
    from rede import rede_pcs
    cfg = carregar_config()
    central = cfg["planilha_central_id"]
    google = BackendGoogle(caminho_chave_google(cfg))

    if args.onde:
        from central.backend_api import BackendAPI
        from central.backend_roteado import token_derivado
        from emails import envio_nf
        url, motivo = virada.url_valida(args.onde)
        if not url:
            sys.exit(f"Endereço recusado: {motivo}")
        do_google = google.ler_abas(central, [envio_nf.ABA_PCS])[0].get(envio_nf.ABA_PCS, [])
        do_servidor = BackendAPI(url, token_derivado(cfg), tempo=30).ler_abas(central, [envio_nf.ABA_PCS])[0].get(envio_nf.ABA_PCS, [])
        onde = virada.onde_estao(do_google, do_servidor)
        for pc, lugar in onde.items():
            print(f"  {pc}: {lugar}")
        if virada.dividido(onde):
            print("ATENCAO: ha PC no servidor e PC no Google ao mesmo tempo. Cada grupo enxerga uma Central diferente: "
                  "reenvie o comando aos que ficaram no Google ou volte todos (--desligar).")
            return 1
        return 0

    if args.ver:
        linhas = google.ler_abas(central, [rede_pcs.ABA_COMANDOS])[0].get(rede_pcs.ABA_COMANDOS, [])
        for linha in linhas[-12:][::-1]:
            linha = list(linha) + [""] * 6
            if rede_pcs.comando_base(linha[3]) in virada.COMANDOS_DA_VIRADA:
                print(f"{linha[0][:19]} {linha[1]} para {linha[2]}: {linha[3]}  ->  {linha[5] or '(sem resposta ainda)'}  [{linha[4]}]")
        return 0

    if args.ligar:
        url, motivo = virada.url_valida(args.ligar)
        if not url:
            sys.exit(f"Endereço recusado: {motivo}")
        comando = f"{virada.COMANDO_LIGAR} {url}"
    else:
        comando = virada.COMANDO_DESLIGAR
    if not args.confirmo:
        sys.exit(f"Vai mandar \"{comando}\" para {args.para}. Isto muda de onde os PCs leem os dados. Repita com --confirmo.")
    google.anexar_linhas(central, rede_pcs.ABA_COMANDOS, [rede_pcs.pedido(args.para, comando, "Claude (a pedido do João)")])
    print(f"Comando enviado: \"{comando}\" para {args.para}. Acompanhe com --ver (os PCs respondem em até 1 minuto).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
