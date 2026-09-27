"""Nova tentativa automática em falha passageira do Google."""
import time

from log_util import configurar_logging

logger = configurar_logging(__name__)


def com_retry(func, deve_tentar_de_novo, tentativas=5, espera_inicial=10, multiplicador=2, esperar=time.sleep):
    """Chama func(). Se der erro passageiro (deve_tentar_de_novo(erro) == True), espera e tenta de novo,…"""
    espera = espera_inicial
    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except Exception as e:
            if tentativa == tentativas or not deve_tentar_de_novo(e):
                raise
            logger.warning(f"⚠️ Tentativa {tentativa}/{tentativas} falhou ({e}) — "
                           f"esperando {espera}s antes de tentar de novo.")
            esperar(espera)
            espera *= multiplicador


def e_erro_passageiro_google(excecao):
    texto = str(excecao)
    return any(codigo in texto for codigo in ("429", "500", "502", "503")) or "timed out" in texto.lower()
