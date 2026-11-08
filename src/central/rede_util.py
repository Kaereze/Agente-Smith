"""Retry com backoff exponencial para erros passageiros da API do Google."""
import time

from sistema.log_util import configurar_logging

logger = configurar_logging(__name__)


def com_retry(func, deve_tentar_de_novo, tentativas=5, espera_inicial=10, multiplicador=2, esperar=time.sleep,
              orcamento=None, relogio=time.monotonic):
    """orcamento (segundos): o tempo TOTAL que a chamada pode levar, contando as esperas. Se a próxima espera estourar o orçamento, para e
    levanta o erro (29/10/2026, pedido do João: volta de minutos virava no máximo 30 s)."""
    espera = espera_inicial
    inicio = relogio()
    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except Exception as e:
            if tentativa == tentativas or not deve_tentar_de_novo(e):
                raise
            if orcamento is not None and relogio() - inicio + espera >= orcamento:
                logger.warning(f"⚠️ Tentativa {tentativa}/{tentativas} falhou ({e}) — sem tempo para tentar de novo (limite de {orcamento:.0f}s).")
                raise
            logger.warning(f"⚠️ Tentativa {tentativa}/{tentativas} falhou ({e}) — "
                           f"esperando {espera}s antes de tentar de novo.")
            esperar(espera)
            espera *= multiplicador


def e_erro_passageiro_google(excecao):
    texto = str(excecao)
    return any(codigo in texto for codigo in ("429", "500", "502", "503")) or "timed out" in texto.lower()
