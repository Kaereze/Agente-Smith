"""Log central: logs/solicitacoes_nf.log."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PASTA_LOGS = Path(__file__).resolve().parent.parent / "logs"


def _rodando_sob_pytest():
    return "PYTEST_VERSION" in os.environ or "pytest" in sys.modules


_JA_CONFIGURADO = False


def configurar_logging(nome):
    global _JA_CONFIGURADO
    if not _JA_CONFIGURADO:
        sob_teste = _rodando_sob_pytest()
        caminho = PASTA_LOGS / ("testes/solicitacoes_nf_teste.log" if sob_teste else "solicitacoes_nf.log")
        caminho.parent.mkdir(parents=True, exist_ok=True)

        formato = logging.Formatter(
            ("[TESTE] " if sob_teste else "") + "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%d/%m/%Y %H:%M:%S",
        )
        arquivo = RotatingFileHandler(caminho, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        arquivo.setFormatter(formato)
        tela = logging.StreamHandler(sys.stdout)
        tela.setFormatter(formato)

        raiz = logging.getLogger()
        raiz.setLevel(logging.INFO)
        raiz.addHandler(arquivo)
        raiz.addHandler(tela)
        _JA_CONFIGURADO = True
    return logging.getLogger(nome)
