"""Liga o servidor central NESTE PC (o "Servidor RA"), sem Docker (API central, etapa 5).

    pythonw ferramentas\\rodar_servidor_central.py [--pasta C:\\ServidorCentral] [--porta 8770]

É o que a tarefa agendada `ServidorCentral` roda (Automacoes\\agendar_servidor_central.ps1). O token sai da chave do Google deste
PC (o mesmo cálculo dos outros PCs), então não há senha para guardar nem para copiar. O banco fica em <pasta>\\central.sqlite
(padrão: C:\\ServidorCentral, fora do projeto, para o git e as atualizações nunca encostarem nele). Se a porta já está em uso (o
servidor já roda), esta cópia sai na hora: a repetição de 10 minutos da tarefa só religa se ele tiver caído.
"""
import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=r"C:\ServidorCentral")
    ap.add_argument("--porta", type=int, default=8770)
    args = ap.parse_args()
    from config import carregar_config
    from central.backend_roteado import token_derivado
    token = token_derivado(carregar_config(exigir_chave=False))
    if not token:
        sys.exit("Este PC não tem a chave do Google: não dá para calcular o token do servidor.")
    pasta = Path(args.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    os.environ["CENTRAL_TOKEN"] = token
    os.environ["CENTRAL_BANCO"] = str(pasta / "central.sqlite")
    os.environ["CENTRAL_PORTA"] = str(args.porta)
    from servidor_central import servidor
    try:
        servidor.main()
    except OSError as e:   # porta ocupada: o servidor já está rodando
        sys.exit(f"Não subi (porta {args.porta}): {e}")


if __name__ == "__main__":
    main()
