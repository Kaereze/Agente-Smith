"""Gera o segredo-rede.txt para levar a um PC novo que tem uma chave do Google diferente (29/10/2026).

Rode no PC do João (ou de qualquer PC que já conversa com os outros):
    .venv\\Scripts\\python.exe Automacoes\\gerar_segredo_rede.py [pasta de destino]

Sem pasta de destino, grava na Área de Trabalho. O arquivo tem só o resumo que os PCs usam para confiar uns nos outros
(a chave privada do Google NÃO vai junto) e o valor nunca aparece na tela. No PC novo ele fica em
%APPDATA%\\SolicitacoesNF\\segredo-rede.txt, ao lado do chave-api.json. Depois de copiar, apague este arquivo daqui.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import rede_local  # noqa: E402
from config import caminho_chave_google, carregar_config  # noqa: E402


def main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / rede_local.ARQUIVO_SEGREDO_REDE
    if not rede_local.gerar_arquivo_segredo(caminho_chave_google(carregar_config()), destino):
        print("Não consegui ler a chave do Google deste PC. Nada foi gerado.")
        return 1
    print(f"Pronto: {destino}")
    print("Leve esse arquivo para o PC novo (cabo, Compartilhamento por proximidade ou o próprio WhatsApp só para você)")
    print("e apague a cópia daqui depois. Ele NÃO contém a chave do Google.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
