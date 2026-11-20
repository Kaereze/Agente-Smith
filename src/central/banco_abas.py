"""Espelho de abas da Planilha Central no banco (Supabase), 20/11/2026: a fila de envio (`Envios_NF`) também mora no banco.

O resto do Painel não muda: ele continua chamando `backend.anexar_linhas`, `backend.ler_abas` e `backend.apagar_linhas`.
`BackendComBanco` fica no meio, só para as abas ligadas em `config.json > banco > abas` (padrão: nenhuma = nada muda):

- modo "sombra": a PLANILHA continua mandando (grava e lê como sempre). Cada linha gravada vai também para o banco, por trás,
  sem atrasar nem derrubar o envio. Serve para conferir que o banco fica igual (`ferramentas/comparar_fila_banco.py`).
- modo "banco": o BANCO manda. Grava no banco primeiro (se falhar, o erro sobe como sobe o do Google) e lê do banco; a planilha
  recebe uma cópia por trás. É o que acelera o envio. SÓ vale com os 4 PCs já gravando no banco; misturar modos entre PCs
  dá fila dividida (cada lado vê um pedaço) e risco de e-mail em dobro.

A fila é uma tabela única `aba_linhas` (aba, valores, criado): cada linha da planilha vira uma linha do banco, na ordem em que
chegou (o `id` do banco decide quem foi primeiro, como a ordem das linhas da planilha decidia). Dado de hóspede: a fila leva
o e-mail do destinatário e o assunto; por isso o banco exige a credencial de cada PC (ver supabase.py e ferramentas/supabase_fila.sql).
"""
import datetime
import queue
import threading
import time

from central.supabase import Banco, ErroBanco, caminho_da_chave
from painel import desempenho
from sistema.log_util import configurar_logging

logger = configurar_logging(__name__)

TABELA = "aba_linhas"
MODOS = ("sombra", "banco")
TENTATIVAS_ESPELHO = 3
ESPERAS_ESPELHO = (2, 6)   # segundos entre as tentativas de gravar a cópia por trás


def abas_suportadas():
    """{aba: cabeçalho}: só as abas que sabemos espelhar. O cabeçalho não é guardado no banco: a linha 1 da planilha é fixa no código."""
    from emails import envio_nf
    return {envio_nf.ABA_FILA: list(envio_nf.CAB_FILA)}


class BackendComBanco:
    """Envolve o backend do Google. Tudo o que não é das abas ligadas passa direto para ele."""

    def __init__(self, google, banco, abas, retencao_dias=None, somente_leitura=False, segundo_plano=True, esperar=time.sleep,
                 relogio=lambda: datetime.datetime.now(datetime.timezone.utc)):
        self._google, self._banco = google, banco
        self._abas = {nome: {"modo": c["modo"], "cabecalho": list(c["cabecalho"])} for nome, c in abas.items()}
        self._retencao = dict(retencao_dias or {})
        self._somente_leitura, self._esperar, self._relogio = somente_leitura, esperar, relogio
        self.gravadas = self.falhas = 0
        self.ultimo_erro = ""
        self._fila = queue.Queue(maxsize=5000)
        self._lock = threading.Lock()
        if segundo_plano and not somente_leitura:
            threading.Thread(target=self._trabalhar, daemon=True, name="espelho_banco").start()
        self._por_tras = segundo_plano

    def __getattr__(self, nome):   # só é chamado quando o atributo não existe aqui: o resto é do backend do Google
        if nome.startswith("_"):
            raise AttributeError(nome)
        return getattr(self._google, nome)

    def modo_de(self, aba):
        return (self._abas.get(aba) or {}).get("modo")

    def resumo(self):
        return {"abas": {a: c["modo"] for a, c in self._abas.items()}, "gravadas": self.gravadas, "falhas": self.falhas,
                "ultimo_erro": self.ultimo_erro, "na_fila": self._fila.qsize()}

    # ---- cópia por trás ----
    def _espelhar(self, tarefa, destino, aba):
        if self._por_tras:
            try:
                self._fila.put_nowait((tarefa, destino, aba))
                return
            except queue.Full:
                self._registrar_falha(destino, aba, "fila de cópias cheia")
                return
        self._executar(tarefa, destino, aba)

    def _trabalhar(self):
        while True:
            tarefa, destino, aba = self._fila.get()
            self._executar(tarefa, destino, aba)

    def _executar(self, tarefa, destino, aba):
        """Tenta algumas vezes; se não der, registra (nunca levanta: a cópia não pode derrubar o envio)."""
        erro = ""
        for i in range(TENTATIVAS_ESPELHO):
            try:
                tarefa()
                with self._lock:
                    self.gravadas += 1
                return
            except Exception as e:
                erro = str(e)[:160]
                if i < len(ESPERAS_ESPELHO):
                    self._esperar(ESPERAS_ESPELHO[i])
        self._registrar_falha(destino, aba, erro)

    def _registrar_falha(self, destino, aba, erro):
        with self._lock:
            self.falhas += 1
            self.ultimo_erro = f"{destino}/{aba}: {erro}"
        logger.warning(f"⚠️ Cópia da aba '{aba}' para {destino} não gravou ({erro}). A aba continua certa na outra ponta.")

    # ---- gravar ----
    def _gravar_banco(self, aba, linhas):
        with desempenho.MEDIDOR.medir("banco.gravar", 5.0, logger):
            self._banco.gravar(TABELA, [{"aba": aba, "valores": l} for l in linhas])

    def anexar_linhas(self, planilha_id, aba, linhas):
        c = self._abas.get(aba)
        if not c or self._somente_leitura or not linhas:
            return self._google.anexar_linhas(planilha_id, aba, linhas)
        linhas = [[str(v) for v in l] for l in linhas]
        if c["modo"] == "banco":
            self._gravar_banco(aba, linhas)   # primeiro e obrigatório: se falhar, o erro sobe e nada foi pedido
            self._espelhar(lambda: self._google.anexar_linhas(planilha_id, aba, linhas), "planilha", aba)
        else:
            self._google.anexar_linhas(planilha_id, aba, linhas)
            self._espelhar(lambda: self._gravar_banco(aba, linhas), "banco", aba)

    # ---- ler ----
    def ler_abas(self, planilha_id, nomes, faixas=None):
        nomes = list(dict.fromkeys(nomes))
        do_banco = [n for n in nomes if self.modo_de(n) == "banco"]
        lidas, erros = self._google.ler_abas(planilha_id, [n for n in nomes if n not in do_banco], faixas) if len(do_banco) < len(nomes) else ({}, {})
        lidas, erros = dict(lidas), dict(erros)
        for aba in do_banco:
            try:
                with desempenho.MEDIDOR.medir("banco.ler", 5.0, logger):
                    linhas = self._banco.ler_tudo(TABELA, {"aba": f"eq.{aba}"}, colunas="valores", ordem="id.asc")
                lidas[aba] = [list(self._abas[aba]["cabecalho"])] + [[str(v) for v in l["valores"]] for l in linhas]
            except ErroBanco as e:
                erros[aba] = f"banco: {e}"
        return lidas, erros

    # ---- faxina ----
    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        c = self._abas.get(aba)
        if not c or self._somente_leitura or novas:
            return self._google.apagar_linhas(planilha_id, aba, inicio, fim, novas)
        if c["modo"] == "banco":   # as posições vieram da leitura do banco: apaga exatamente essas linhas
            ids = self._banco.ler(TABELA, {"aba": f"eq.{aba}"}, colunas="id", ordem="id.asc", limite=max(fim - inicio, 0), desloc=max(inicio - 2, 0))
            if ids:
                self._banco.apagar(TABELA, {"id": "in.(" + ",".join(str(x["id"]) for x in ids) + ")"})
            return None
        self._google.apagar_linhas(planilha_id, aba, inicio, fim, novas)   # sombra: a planilha manda; o banco limpa por idade
        dias = self._retencao.get(aba)
        if dias:
            corte = (self._relogio() - datetime.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._espelhar(lambda: self._banco.apagar(TABELA, {"aba": f"eq.{aba}", "criado": f"lt.{corte}"}), "banco", aba)
        return None


def envolver(backend, cfg, somente_leitura=False, segundo_plano=True):
    """Devolve o backend com o espelho ligado, ou o mesmo backend se nada está ligado (`banco.abas` vazio ou sem o arquivo da chave)."""
    pedidas = (cfg.get("banco") or {}).get("abas") or {}
    suportadas = abas_suportadas()
    for nome in pedidas:
        if nome not in suportadas:
            logger.warning(f"⚠️ banco.abas: '{nome}' ainda não pode ser espelhada no banco — ignorada.")
    abas = {n: {"modo": m, "cabecalho": suportadas[n]} for n, m in pedidas.items() if n in suportadas and m in MODOS}
    for nome, modo in pedidas.items():
        if nome in suportadas and modo not in MODOS:
            logger.warning(f"⚠️ banco.abas: modo '{modo}' da aba '{nome}' não existe (use 'sombra' ou 'banco') — ignorada.")
    if not abas:
        return backend
    caminho = caminho_da_chave(cfg)
    try:
        banco = Banco.do_arquivo(caminho)
    except ErroBanco as e:
        logger.error(f"❌ banco.abas está ligado mas o banco não abriu: {e}. Seguindo só com a planilha.")
        return backend
    from central import faxina
    logger.info("🗄️ Banco central ligado para: " + ", ".join(f"{n} ({c['modo']})" for n, c in abas.items()))
    return BackendComBanco(backend, banco, abas, retencao_dias={n: faxina.DIAS_REGISTROS for n in abas},
                           somente_leitura=somente_leitura, segundo_plano=segundo_plano)
