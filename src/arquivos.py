"""Gravação atômica de JSON."""
import json
import os
import time

TENTATIVAS = 6


def salvar_json(caminho, dados, indent=1):
    caminho = str(caminho)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=indent)
    # Antivírus/indexador às vezes segura o arquivo por instantes (WinError 5)
    for tentativa in range(TENTATIVAS):
        try:
            os.replace(temporario, caminho)
            return
        except PermissionError:
            if tentativa == TENTATIVAS - 1:
                raise
            time.sleep(0.5 * (tentativa + 1))


# Arquivo "somente online" do Dropbox: abrir faz o Dropbox baixar e guardar no PC.
_SO_NA_NUVEM = 0x1000 | 0x40000 | 0x400000   # OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS


def so_na_nuvem(caminho):
    """True se o arquivo ainda não foi baixado — lê-lo puxaria o arquivo inteiro pro disco."""
    try:
        return bool(getattr(os.stat(caminho), "st_file_attributes", 0) & _SO_NA_NUVEM)
    except OSError:
        return False
