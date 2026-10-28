"""Medidor de desempenho (28/10/2026, pedido do João: "deixar o programa mais otimizado e fluido").

Só MEDE: não muda o comportamento de nada. Cronometra os laços do Painel e do conferente e as respostas do servidor,
guarda os últimos tempos na memória (até 200 por etapa) e escreve no log só o que passa do limite (no máximo 1 aviso por
minuto por etapa, para não encher o log). Medir antes de mexer: com os números dá para otimizar o que pesa de verdade.

Só guarda o NOME da etapa e os segundos. Nenhum dado de hóspede entra aqui (a rota HTTP é cortada antes do "?").
O servidor mostra o resumo em /api/desempenho (só o administrador); o conferente, que é outro programa, escreve um
resumo no próprio log a cada 10 min.
"""
import collections
import contextlib
import logging
import re
import threading
import time

LIMITE_LACO_S = 30.0       # volta do Painel ou do conferente que passa disso vira aviso (promessa feita ao João em 28/10/2026)
LIMITE_HTTP_S = 1.0        # resposta do servidor à tela
GUARDAR = 200              # últimos tempos de cada etapa (para a média e o p95)
MAX_ETAPAS = 80            # trava contra nomes sem fim
AVISO_A_CADA_S = 60        # no máximo 1 aviso por minuto para cada etapa
RESUMO_A_CADA_S = 600

_PUBLICAS = re.compile(r"^/(fontes|pecas|assinaturas)/")


def rota_curta(caminho, verbo="GET"):
    """'/api/correio/texto?id=…' -> 'GET /api/correio/texto'. Arquivo público (fonte, peça, imagem) vira 1 etapa só."""
    caminho = str(caminho or "").split("?", 1)[0].split("#", 1)[0]
    if caminho in ("", "/", "/index.html"):
        return f"{verbo} página"
    m = _PUBLICAS.match(caminho)
    return f"{verbo} /{m.group(1)}/*" if m else f"{verbo} {caminho[:60]}"


class Medidor:
    def __init__(self, relogio=time.perf_counter, agora=time.monotonic):
        self._relogio, self._agora = relogio, agora
        self._lock = threading.Lock()
        self._recentes = {}        # etapa -> últimos tempos (s)
        self._totais = {}          # etapa -> [quantas, maior (s), lentas, último (s)]
        self._soma = {}            # etapa -> soma dos tempos (s)
        self._ultimo_aviso = {}
        self._ultimo_resumo = agora()

    def registrar(self, etapa, segundos, limite=None, logger=None):
        with self._lock:
            if etapa not in self._totais and len(self._totais) >= MAX_ETAPAS:
                etapa = "outras"
            t = self._totais.setdefault(etapa, [0, 0.0, 0, 0.0])
            self._soma[etapa] = self._soma.get(etapa, 0.0) + segundos
            self._recentes.setdefault(etapa, collections.deque(maxlen=GUARDAR)).append(segundos)
            t[0] += 1
            t[1] = max(t[1], segundos)
            t[3] = segundos
            lenta = limite is not None and segundos > limite
            avisar = False
            if lenta:
                t[2] += 1
                agora = self._agora()
                if agora - self._ultimo_aviso.get(etapa, -AVISO_A_CADA_S) >= AVISO_A_CADA_S:
                    self._ultimo_aviso[etapa] = agora
                    avisar = True
        if avisar:
            (logger or logging.getLogger("desempenho")).warning(
                f"⏱️ Lento: {etapa} levou {segundos:.1f} s (limite {limite:.0f} s). Medindo para saber o que pesa.")

    @contextlib.contextmanager
    def medir(self, etapa, limite=LIMITE_LACO_S, logger=None):
        """with MEDIDOR.medir("painel.atualizar"): ...  Registra mesmo se der erro, e deixa o erro seguir."""
        inicio = self._relogio()
        try:
            yield
        finally:
            self.registrar(etapa, self._relogio() - inicio, limite, logger)

    def resumo(self):
        """{etapa: {n, ultimo_ms, medio_ms, p95_ms, max_ms, lentas}}, da mais pesada (média) para a mais leve."""
        with self._lock:
            copia = {e: (list(self._recentes[e]), list(t), self._soma.get(e, 0.0)) for e, t in self._totais.items()}
        saida = {}
        for etapa, (recentes, (n, maior, lentas, ultimo), soma) in copia.items():
            ordenados = sorted(recentes)
            p95 = ordenados[int(0.95 * (len(ordenados) - 1))] if ordenados else 0.0
            saida[etapa] = {"n": n, "ultimo_ms": round(ultimo * 1000), "medio_ms": round(soma / n * 1000) if n else 0,
                            "p95_ms": round(p95 * 1000), "max_ms": round(maior * 1000), "lentas": lentas}
        return dict(sorted(saida.items(), key=lambda kv: -kv[1]["medio_ms"]))

    def linha_de_resumo(self, topo=6):
        itens = list(self.resumo().items())[:topo]
        return "; ".join(f"{e}: média {v['medio_ms']} ms, p95 {v['p95_ms']} ms, máx {v['max_ms']} ms ({v['n']}×)" for e, v in itens)

    def talvez_resumir(self, logger, cada_s=RESUMO_A_CADA_S):
        """De tempos em tempos escreve no log as etapas mais pesadas (para o conferente, que não tem tela de medição)."""
        agora = self._agora()
        if agora - self._ultimo_resumo < cada_s:
            return False
        self._ultimo_resumo = agora
        linha = self.linha_de_resumo()
        if linha:
            logger.info(f"⏱️ Desempenho (etapas mais pesadas): {linha}")
        return bool(linha)


MEDIDOR = Medidor()
