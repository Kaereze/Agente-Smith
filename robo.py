"""Entrada do robô de envio (Bat/executar_robo.bat)."""
import datetime
import os
import sys
import traceback

PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_FALHA_CRITICA = os.path.join(PASTA_PROJETO, "FALHA_CRITICA.txt")


def main():
    try:
        sys.path.insert(0, os.path.join(PASTA_PROJETO, "src"))
        from main import rodar
        codigo = rodar()
    except Exception:
        texto = (
            "FALHA CRÍTICA — o robô Solicitações NF não conseguiu nem iniciar\n"
            f"Data/hora: {datetime.datetime.now():%d/%m/%Y %H:%M:%S}\n"
            f"Máquina: {os.environ.get('COMPUTERNAME', '?')}\n"
            f"Python: {sys.version}\n\n{traceback.format_exc()}"
        )
        try:
            with open(CAMINHO_FALHA_CRITICA, "w", encoding="utf-8") as f:
                f.write(texto)
        except Exception:
            pass
        print(texto)
        codigo = 1
    sys.exit(codigo)


if __name__ == "__main__":
    main()
