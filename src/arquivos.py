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
