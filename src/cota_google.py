"""Orçamento da cota do Google Sheets, dividido entre os programas dos 4 PCs.

A conta de serviço é uma só pra todos: o Google aceita 60 leituras e 60 escritas por minuto, SOMANDO os 4 PCs.
Cada programa recebe uma fatia fixa (tabela abaixo) e nunca passa dela: se chegar no limite, espera uns segundos
em vez de estourar a cota de todo mundo. A soma das fatias fica abaixo de 60, então um PC não derruba o outro.

  leituras/min   painel   conferente   sincronizar(*)   ×PCs   total
  PC comum          6         4             —            3      30
  PC principal      6         9             8            1      23 + vigia dos formulários 4 = 27   -> 57 de 60
  (*) a cópia das planilhas dos hotéis só roda no principal; o conferente do principal atende o menu ⚡ (6/min).

Cada programa grava o próprio consumo em estado/cota_google/<perfil>.json; o Painel soma e publica na PCs_Painel,
e o Monitoramento mostra "Cota do Google: 31 de 60".
"""
import collections
import json
import os
import threading
import time

from config import PASTA_ESTADO

LIMITE_GOOGLE = 60
PERFIS = {   # perfil: (leituras/min, escritas/min)
    "painel": (6, 6),   # 23/10/2026: era 7; a leitura de 15 s usa ~4/min. A sobra vai pra vigia dos formulários
    "conferente": (4, 5),
    "conferente_principal": (9, 8),
    "sincronizar": (8, 6),
    "vigia_formularios": (4, 3),   # cópia rápida, linha própria dentro do conferente do principal (23/10/2026)
    "padrao": (4, 4),
}
PASTA_CONSUMO = PASTA_ESTADO / "cota_google"
GRAVAR_CONSUMO_SEGUNDOS = 30
PAUSA_APOS_429 = 20


class Cota:
    def __init__(self, perfil="padrao", relogio=time.monotonic, esperar=time.sleep):
        self.relogio, self.esperar = relogio, esperar
        self.lock = threading.Lock()
        self.marcas = {"leitura": collections.deque(), "escrita": collections.deque()}
        self.pausa_ate = 0.0
        self.esperas = 0          # quantas vezes precisou segurar (pra mostrar no Monitoramento)
        self.gravado_em = -1e9
        self.definir(perfil)

    def definir(self, perfil):
        self.perfil = perfil if perfil in PERFIS else "padrao"
        self.limites = dict(zip(("leitura", "escrita"), PERFIS[self.perfil]))

    def _limpar(self, agora):
        for fila in self.marcas.values():
            while fila and agora - fila[0] >= 60:
                fila.popleft()

    def usar(self, tipo):
        """Marca 1 chamada; se a fatia do minuto acabou (ou o Google pediu pausa), espera a vez."""
        while True:
            with self.lock:
                agora = self.relogio()
                self._limpar(agora)
                fila = self.marcas[tipo]
                if agora >= self.pausa_ate and len(fila) < self.limites[tipo]:
                    fila.append(agora)
                    break
                espera = max(self.pausa_ate - agora, (60 - (agora - fila[0]) + 0.05) if fila else 1)
                self.esperas += 1
            self.esperar(min(max(espera, 0.05), 60))
        self._gravar_consumo()

    def pausar(self, segundos=PAUSA_APOS_429):
        """O Google respondeu 429 (cota): o programa inteiro segura um pouco, não só a chamada que falhou."""
        with self.lock:
            self.pausa_ate = max(self.pausa_ate, self.relogio() + segundos)

    def consumo(self):
        with self.lock:
            self._limpar(self.relogio())
            return {"perfil": self.perfil, "leituras": len(self.marcas["leitura"]), "escritas": len(self.marcas["escrita"]),
                    "limite_leituras": self.limites["leitura"], "limite_escritas": self.limites["escrita"],
                    "esperas": self.esperas}

    def _gravar_consumo(self):
        agora = self.relogio()
        if agora - self.gravado_em < GRAVAR_CONSUMO_SEGUNDOS:
            return
        self.gravado_em = agora
        try:
            PASTA_CONSUMO.mkdir(parents=True, exist_ok=True)
            dados = {**self.consumo(), "quando": time.time(), "pid": os.getpid()}
            caminho = PASTA_CONSUMO / f"{self.perfil}.json"
            temporario = caminho.with_suffix(".tmp")
            temporario.write_text(json.dumps(dados), encoding="utf-8")
            os.replace(temporario, caminho)
        except OSError:
            pass


COTA = Cota()
_LINHA = threading.local()


def usar_nesta_linha(perfil):
    """Esta linha de execução (thread) passa a contar numa fatia própria (a vigia dos formulários dentro do conferente
    não come a fatia dele). As outras linhas continuam na COTA do programa."""
    _LINHA.cota = Cota(perfil)
    return _LINHA.cota


def da_linha():
    """A fatia própria desta linha (usar_nesta_linha) ou None."""
    return getattr(_LINHA, "cota", None)


def atual():
    return da_linha() or COTA


def configurar(perfil):
    """Chamado no início de cada programa (painel, conferente, sincronizar)."""
    COTA.definir(perfil)


def consumo_deste_pc(validade=180):
    """Soma do que os programas deste PC usaram no último minuto -> (leituras, escritas)."""
    leituras = escritas = 0
    agora = time.time()
    for arquivo in PASTA_CONSUMO.glob("*.json") if PASTA_CONSUMO.exists() else []:
        try:
            d = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if agora - float(d.get("quando", 0)) <= validade:
            leituras += int(d.get("leituras", 0))
            escritas += int(d.get("escritas", 0))
    return leituras, escritas


def e_cota_estourada(erro):
    texto = str(erro)
    return "429" in texto or "RESOURCE_EXHAUSTED" in texto or "Quota exceeded" in texto
