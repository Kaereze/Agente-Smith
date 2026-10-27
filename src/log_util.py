"""Log de cada programa em logs/ (20/10/2026): robô = solicitacoes_nf.log, conferente.log, painel.log.

Antes os três escreviam no mesmo solicitacoes_nf.log; ao girar (5 MB) o Windows não deixava renomear um arquivo aberto
por outro processo (PermissionError WinError 32) e cada linha virava um "Logging error" na saída da tela (14.017 até
20/10/2026). Com um arquivo por programa, só quem escreve gira o seu.
"""
import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PASTA_LOGS = Path(__file__).resolve().parent.parent / "logs"

# script de entrada -> arquivo de log (o robô fica no nome antigo: o manual e os avisos da tela apontam pra ele)
PROGRAMAS = {"sincronizar": "solicitacoes_nf", "robo": "solicitacoes_nf", "main": "solicitacoes_nf",
             "conferente": "conferente", "app_servidor": "painel", "app_janela": "painel"}


# E-mail de hóspede não fica nos registros técnicos (27/10/2026, LGPD): vira m***@gmail.com. Fica inteiro o que é da
# empresa (caixas dos hotéis, agentes), que o suporte precisa ler.
_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_DA_EMPRESA = ("redeandrade", "andradehoteis", "hotel", "exemplo")


def mascarar_emails(texto):
    def troca(m):
        dominio = m.group(1).lower()
        if any(p in dominio for p in _DA_EMPRESA):
            return m.group(0)
        return m.group(0)[:1] + "***@" + m.group(1)
    return _EMAIL.sub(troca, texto)


class _MascaraDeEmail(logging.Filter):
    def filter(self, registro):
        try:
            registro.msg, registro.args = mascarar_emails(registro.getMessage()), None
        except Exception:
            pass
        return True


def _rodando_sob_pytest():
    return "PYTEST_VERSION" in os.environ or "pytest" in sys.modules


def arquivo_do_programa(script=None):
    """Nome do arquivo de log do programa que está rodando (pelo script de entrada, sys.argv[0])."""
    script = script if script is not None else (sys.argv[0] if sys.argv else "")
    if not str(script).lower().endswith(".py"):
        return "outros.log"
    nome = Path(str(script).replace("\\", "/")).stem
    return PROGRAMAS.get(nome, "".join(c for c in nome if c.isalnum() or c == "_") or "outros") + ".log"


_JA_CONFIGURADO = False


def configurar_logging(nome):
    global _JA_CONFIGURADO
    if not _JA_CONFIGURADO:
        sob_teste = _rodando_sob_pytest()
        caminho = PASTA_LOGS / ("testes/solicitacoes_nf_teste.log" if sob_teste else arquivo_do_programa())
        caminho.parent.mkdir(parents=True, exist_ok=True)

        formato = logging.Formatter(
            ("[TESTE] " if sob_teste else "") + "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%d/%m/%Y %H:%M:%S",
        )
        arquivo = RotatingFileHandler(caminho, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        arquivo.setFormatter(formato)
        arquivo.addFilter(_MascaraDeEmail())
        tela = logging.StreamHandler(sys.stdout)
        tela.setFormatter(formato)
        tela.addFilter(_MascaraDeEmail())

        raiz = logging.getLogger()
        raiz.setLevel(logging.INFO)
        raiz.addHandler(arquivo)
        raiz.addHandler(tela)
        _JA_CONFIGURADO = True
    return logging.getLogger(nome)
