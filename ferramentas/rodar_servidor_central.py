"""Liga o servidor central NESTE PC (o "Servidor RA"), sem Docker (API central, etapa 5).

    pythonw ferramentas\\rodar_servidor_central.py [--pasta C:\\ServidorCentral] [--porta 8770] [--appdata C:\\Users\\X\\AppData\\Roaming]

É o que a tarefa agendada `ServidorCentral` roda (Automacoes\\agendar_servidor_central.ps1), como SISTEMA, logo que o Windows
liga (ninguém precisa entrar). O token sai da chave do Google deste PC (o mesmo cálculo dos outros PCs), então não há senha
para guardar nem para copiar. A chave fica em %APPDATA%\\SolicitacoesNF\\chave-api.json, na pasta do usuário; como SISTEMA o
%APPDATA% é outro, e por isso a tarefa passa --appdata com a pasta do usuário que a instalou. O banco fica em
<pasta>\\central.sqlite (padrão: C:\\ServidorCentral, fora do projeto, para o git e as atualizações nunca encostarem nele). Se a
porta já está em uso (o servidor já roda), esta cópia sai na hora: a repetição de 10 minutos da tarefa só religa se ele tiver caído.
"""
import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def aplicar_appdata(valor):
    """Aponta %APPDATA% para a pasta do usuário que instalou a tarefa (vazio = deixa como está). Tem que vir antes de ler o config."""
    if valor:
        os.environ["APPDATA"] = valor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", default=r"C:\ServidorCentral")
    ap.add_argument("--porta", type=int, default=8770)
    ap.add_argument("--appdata", default="", help="pasta AppData\\Roaming do usuário (onde está a chave do Google); só para rodar como SISTEMA")
    args = ap.parse_args()
    aplicar_appdata(args.appdata)
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
