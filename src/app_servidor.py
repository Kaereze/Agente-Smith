"""Painel Notas Fiscais: servidor HTTP só em 127.0.0.1 + janela do Edge em modo aplicativo.

    python src\\app_servidor.py --sem-janela   servidor em segundo plano (tarefa SolicitacoesNF_Painel, no logon)
    python src\\app_servidor.py                abre a janela; liga o servidor antes se ele não estiver rodando

O servidor fica no ar enquanto o PC estiver ligado e mantém os dados atualizados, então a
janela abre já carregada. O último estado também vai pro disco (painel_cache.pkl) pra
sobreviver a um reinício. Todos os PCs leem e gravam a mesma Planilha Central.
"""
import datetime
import gzip
import hashlib
import json
import os
import pickle
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
import atividade
import atualizador
import avisos_windows
import canceladas
import hospedes
import ligacoes
import cota_google
import envio_nf
import espelho_emails
import rede_local
import rede_pcs
import contagem_painel
import relatorio_semana
import saude
import fiscal_intelligence
import painel_metricas as metricas
import agentes_smith
import rotas_api
import desempenho
from arquivos import salvar_json
from hoteis import CadastroHoteis
from app_envio import Envio
from estado_sistema import DROPBOX_OLHAR_SEGUNDOS, REINICIO_PENDENTE_MIN, SistemaMixin   # noqa: F401
from estado_envio import EnvioMixin
from estado_rede import RedeMixin, VERIFICAR_ATUALIZACAO_MINUTOS, TELAS, SEM_REDE_SEGUNDOS, JANELA_ABERTA_SEGUNDOS, ATIVIDADE_CACHE_SEGUNDOS   # noqa: F401
from estado_correio import CorreioMixin, ENVIADOS_RAPIDO_SEGUNDOS, NOTAS_EMAILS_SEGUNDOS, _kw_ligacao   # noqa: F401  (nomes usados por testes e rotas)
from config import PASTA_ESTADO, PASTA_LOGS, PASTA_PROJETO, caminho_chave_google, carregar_config, e_principal, sem_outlook
import limpeza
from log_util import configurar_logging
from sheets import (STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba)
from tratamento import normalizar

logger = configurar_logging("app")

PORTA = 8765
PASTA_UI = PASTA_PROJETO / "app_ui"
CAMINHO_PREFS = PASTA_ESTADO / "app.json"


def _marca_pagina():
    """Marca da versão da tela (data do arquivo mais novo em app_ui): mudou = a janela aberta recarrega sozinha
    (13/10/2026: a tela foi atualizada sem reiniciar o Painel e a janela continuava com a página antiga)."""
    try:
        arquivos = [*PASTA_UI.iterdir(), *(PASTA_UI / "pecas").glob("*")]   # pecas/: peças únicas (20/10/2026)
        return str(int(max(p.stat().st_mtime for p in arquivos if p.suffix in (".html", ".js", ".css"))))
    except (OSError, ValueError):
        return ""


class ServidorPainel(ThreadingHTTPServer):
    """Fila de conexões maior (21/10/2026): com a fila padrão (5), o servidor ocupado (logo depois de reiniciar) fazia o
    Windows recusar parte dos arquivos da tela, a página abria pela metade e ficava a "tela verde" sem função."""
    request_queue_size = 128


def _pagina_inteira(tentativas=6):
    """index.html lido inteiro: durante uma atualização o arquivo pode estar sendo regravado (lido pela metade = página quebrada)."""
    html = ""
    for _ in range(tentativas):
        html = (PASTA_UI / "index.html").read_text(encoding="utf-8", errors="replace")
        if html.rstrip().endswith("</html>"):
            return html
        time.sleep(0.25)
    return html
CAMINHO_CACHE = PASTA_ESTADO / "painel_cache.pkl"
CAMINHO_CANCELADAS = PASTA_ESTADO / "canceladas.json"
CANCELADAS_MINUTOS = 10
CAMINHO_VERSAO = PASTA_ESTADO / "versao_rodando.txt"
SALVAR_CACHE_SEGUNDOS = 120
VERSAO_CACHE = 1
VOLATEIS_TELA = {"atualizado_em", "visto", "dias"}   # mudam sozinhos a cada volta: fora da comparação do "igual"
VOLATEIS_JUNTO = ("atualizado_em", "pcs")            # ... e estes vão junto com o {"__igual"} (cabeçalho em dia)
ACORDAR_MIN_SEGUNDOS = 12     # novidade do robô relê na hora, mas no máximo 1 vez a cada 12 s (cota do Google: 7/min)
# Leitura leve (08/10/2026): a cada 15 s o Painel baixava ~11 MB (abas dos hotéis + Tratamento inteira). Agora:
HOTEIS_SEGUNDOS = 120              # abas dos hotéis: só mudam com a cópia de 30 em 30 min -> relidas a cada 2 min
TRATAMENTO_COMPLETO_SEGUNDOS = 600 # Tratamento: a cada 15 s só as linhas novas; inteira a cada 10 min (garantia)
JANELA_PAINEL_DIAS = 120
RESOLVIDA_HORAS = 24               # solicitação resolvida fica 24 h na lista e some (o Outlook/planilha guardam)
ESTATICOS = {   # lista fechada: nada fora daqui é servido do disco
    "/icone.png": ("icone.png", "image/png"),
    "/favicon.ico": ("icone.ico", "image/x-icon"),
    "/graficos.js": ("graficos.js", "text/javascript; charset=utf-8"),
    "/painel.js": ("painel.js", "text/javascript; charset=utf-8"),
    "/correio.js": ("correio.js", "text/javascript; charset=utf-8"),
    "/robo.js": ("robo.js", "text/javascript; charset=utf-8"),
    "/fontes/fontes.css": ("fontes/fontes.css", "text/css; charset=utf-8"),
}
ESTATICOS.update({f"/fontes/{f.name}": (f"fontes/{f.name}", "font/woff2") for f in (PASTA_UI / "fontes").glob("*.woff2")})
ESTATICOS.update({f"/pecas/{f.name}": (f"pecas/{f.name}", "text/javascript; charset=utf-8" if f.suffix == ".js" else "text/css; charset=utf-8")
                  for f in (PASTA_UI / "pecas").glob("*") if f.suffix in (".js", ".css")})   # peças únicas (20/10/2026)
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def ler_prefs():
    """Preferências DESTE PC (estado/app.json): operador e tema da tela."""
    try:
        return json.load(open(CAMINHO_PREFS, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def salvar_pref(chave, valor):
    salvar_json(CAMINHO_PREFS, {**ler_prefs(), chave: valor})   # junta: trocar o tema não apaga o operador


TEMAS_OK = ("", "light", "dark")


def nome_do_agente():
    try:
        nome = json.load(open(CAMINHO_PREFS, encoding="utf-8")).get("agente")
        if nome:
            return nome
    except (FileNotFoundError, ValueError):
        pass
    try:
        import identidade
        if identidade.ler().get("agente"):
            return identidade.ler()["agente"]
    except Exception:
        pass
    return os.environ.get("USERNAME", "?")


class Estado(CorreioMixin, RedeMixin, EnvioMixin, SistemaMixin):
    """Cache em memória da Central. Uma leitura (batch) por atualização, pra caber na cota da API."""

    def _caminho_versao(self):
        return CAMINHO_VERSAO

    def _agente(self):   # o correio pergunta aqui, sem importar este módulo (que roda como __main__)
        return nome_do_agente()

    def __init__(self, backend, cfg, relogio=time.monotonic, servico_envio=None):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.envio_nf = servico_envio or envio_nf.ServicoEnvio(backend, cfg, socket.gethostname(), self.registrar_nf_enviada)
        self.envio_nf.segundo_plano = lambda trabalho: threading.Thread(target=trabalho, daemon=True, name="envio_nf").start()   # noqa: E731
        self.envio_nf.entry_confere = lambda i, e, c: bool(getattr(self, "indice", None) and self.indice.confere(i, e, c))   # noqa: E731
        if sem_outlook(cfg):
            self.envio_nf.ler_contas = lambda: []   # PC só com o Painel: nenhuma caixa aqui, o PC dono de cada caixa é quem envia
        self.envio_nf.avisar_dono = self._avisar_dono_envio   # envio direto pela rede (21/10/2026)
        self.central = cfg["planilha_central_id"]
        self.lock = threading.Lock()
        self.abas_hotel, self.abas_lidas_em = {}, -1e9
        self.solicitacoes, self.estados, self.status = [], {}, {}
        self.atualizado_em, self.erro = None, ""
        self.cadastro = CadastroHoteis([])
        painel = cfg.get("painel", {})
        self._desde_cfg = datetime.date.fromisoformat(painel.get("desde", "2026-09-01"))
        self.fi_id, self.fi_minutos = painel.get("fiscal_intelligence_id", ""), int(painel.get("fi_minutos", 5))
        self.ignorar = list(painel.get("ignorar_hoteis", []))
        self.fi, self.fi_lido, self.fi_erro = None, -1e9, ""
        self.canceladas, self.canceladas_lidas, self.lendo_canceladas = [], -1e9, False
        self.cache_salvo = -1e9
        # rede de PCs: Outlook, versão, pedidos novos, comandos e atualização automática
        self.versao = envio_nf.versao_do_codigo() or atualizador.versao()   # lê o .git: nem todo PC tem git no PATH
        self.outlook, self.chaves_vistas, self.versao_registrada = None, None, False
        self.atualizacao = {"verificado_em": "", "motivo": "", "atras": 0}
        self.proxima_verificacao = time.monotonic() + 120
        self.comandos_em_execucao = set()
        self.atividade_cache = ([], -1e9)
        self.envio_nf.extras = self._extras_pc
        self.envio_nf.caixas_de_hotel = self._caixas_de_hotel   # e-mail do robô pela fila (envio_pc_dono)
        self.abas_emails, self.emails = [], []
        self.avisos = avisos_windows.Avisos()
        self.notas_emails, self.notas_emails_em = {}, -1e9   # {id do e-mail: [NF do Dropbox]} — calculado em segundo plano
        self.acordar = threading.Event()   # o robô gravou novidade na Central: o laço relê sem esperar os 15 s
        self.versao_tela = 0               # muda quando a tela tem o que buscar (a tela pergunta a cada 3 s)
        self.marca_dropbox, self.dropbox_olhado = None, -1e9
        self.trat_linhas, self.trat_lido_em, self.hoteis_lidos_em = None, -1e9, -1e9
        self.eventos_linhas, self.eventos_pendentes = [], []   # lido/não lido: gravados juntos, 1 escrita por volta
        self.ligacoes_linhas, self.ligacoes = None, {}     # pedido por ligação (22/10/2026): aba Ligacoes e as marcadas
        self.eventos_correio, self.enviados_correio, self.convs = {}, [], []
        self.abas_textos, self.textos_cache = [], {}           # {pc: (versão, {id: (texto, citado)})}
        self.rede_ligada, self.segredo = False, b""
        self.urgencias_avisadas = None

    @property
    def desde(self):
        """Primeiro dia que o Painel mostra: o do config, mas no máximo 120 dias pra trás (a faxina guarda 150)."""
        return max(self._desde_cfg, datetime.date.today() - datetime.timedelta(days=JANELA_PAINEL_DIAS))

    def _abas(self):
        # PC sem a aba CaixaPedidos_ (ainda não atualizou): procura abas novas a cada 2 min em vez de 10
        faltam = len(getattr(self, "abas_pedidos", [])) < len(getattr(self, "abas_emails", [])) or not getattr(self, "abas_pedidos", [])
        if self.relogio() - self.abas_lidas_em > (120 if faltam else 600):
            marcador = normalizar(self.cfg.get("marcador_aba_respostas", "(respostas)"))
            ignoradas = {normalizar(a) for a in self.cfg.get("abas_ignoradas", [])}
            todas = self.backend.listar_abas(self.central)
            aba_cad = self.cfg["aba_cadastro_hoteis"]
            cad, _ = self.backend.ler_abas(self.central, [aba_cad])
            self.cadastro = CadastroHoteis(cad.get(aba_cad, []), self.cfg.get("apelidos_hoteis", {}),
                                           self.cfg.get("cadastro_colunas"))
            self.abas_hotel = {a: self.cadastro.canonico(nome_do_hotel_pela_aba(a)) or nome_do_hotel_pela_aba(a)
                               for a in todas if marcador in normalizar(a) and normalizar(a) not in ignoradas}
            self.abas_emails = [a for a in todas if a.startswith(espelho_emails.PREFIXO_ABA)]
            self.abas_textos = [a for a in todas if a.startswith(espelho_emails.PREFIXO_TEXTOS)]
            self.abas_pedidos = [a for a in todas if a.startswith(espelho_emails.PREFIXO_PEDIDOS)]
            for aba, cab in ((dados.ABA_TRATAMENTO, dados.CABECALHO_TRATAMENTO), (envio_nf.ABA_FILA, envio_nf.CAB_FILA),
                             (espelho_emails.ABA_EVENTOS, espelho_emails.CAB_EVENTOS),
                             (envio_nf.ABA_ANEXOS, envio_nf.CAB_ANEXOS), (envio_nf.ABA_PCS, envio_nf.CAB_PCS),
                             (atividade.ABA, atividade.CABECALHO), (rede_pcs.ABA_COMANDOS, rede_pcs.CAB_COMANDOS),
                             (ligacoes.ABA, ligacoes.CABECALHO)):
                if aba not in todas:
                    self.backend.criar_aba_log(self.central, aba, cab)
            if hasattr(self.backend, "garantir_colunas"):
                try:
                    self.backend.garantir_colunas(self.central, envio_nf.ABA_PCS, envio_nf.CAB_PCS)
                except Exception as e:
                    logger.warning(f"⚠️ Não consegui aumentar as colunas de {envio_nf.ABA_PCS} ({e})")
            self.abas_lidas_em = self.relogio()
        return self.abas_hotel

    def atualizar(self, completo=False):
        """1 leitura (lote) por volta. As abas dos hotéis entram a cada 2 min; a Tratamento vem só do fim (linhas
        novas): o que se baixa a cada 15 s caiu de ~11 MB pra poucos KB."""
        try:
            abas = self._abas()
            agora = self.relogio()
            status_aba = self.cfg["aba_status"]
            ler_hoteis = completo or not self.solicitacoes or agora - self.hoteis_lidos_em >= HOTEIS_SEGUNDOS
            trat_inteira = completo or self.trat_linhas is None or agora - self.trat_lido_em >= TRATAMENTO_COMPLETO_SEGUNDOS
            self._gravar_eventos_pendentes()
            nomes = [dados.ABA_TRATAMENTO, status_aba, envio_nf.ABA_FILA, envio_nf.ABA_PCS, rede_pcs.ABA_COMANDOS,
                     espelho_emails.ABA_EVENTOS] + self.abas_emails + list(getattr(self, "abas_pedidos", [])) + \
                (list(abas) if ler_hoteis else []) + \
                ([ligacoes.ABA] if ler_hoteis or self.ligacoes_linhas is None else [])   # muda pouco: junto com os hotéis
            # do fim conhecido em diante (a última linha de novo: confere que nada mudou por baixo, ex. faxina)
            faixas = {} if trat_inteira else {dados.ABA_TRATAMENTO: f"A{len(self.trat_linhas)}:H"}
            lidas, erros = self.backend.ler_abas(self.central, nomes, faixas=faixas)
            if not lidas:
                raise RuntimeError(next(iter(erros.values()), "leitura vazia"))
            sumidas = [a for a in erros if a in self.abas_emails or a == espelho_emails.ABA_EVENTOS
                       or a in getattr(self, "abas_pedidos", [])]
            if sumidas:   # aba de passagem apagada/renomeada: some da lista e a lista é refeita na próxima volta
                self.abas_emails = [a for a in self.abas_emails if a not in sumidas]
                self.abas_pedidos = [a for a in getattr(self, "abas_pedidos", []) if a not in sumidas]
                self.abas_lidas_em = -1e9
            lidas_trat = lidas.get(dados.ABA_TRATAMENTO)
            if lidas_trat is None and not trat_inteira:
                # "exceeds grid limits": a aba ficou menor que o fim que eu conhecia (faxina) — relê inteira
                toda = self.backend.ler_abas(self.central, [dados.ABA_TRATAMENTO])[0]
                lidas_trat, trat_inteira = toda.get(dados.ABA_TRATAMENTO), dados.ABA_TRATAMENTO in toda
            trat, novas = self._juntar_tratamento(lidas_trat, trat_inteira)
            if ler_hoteis:
                solicitacoes = []
                for aba, hotel in abas.items():
                    solicitacoes += dados.ler_solicitacoes(aba, hotel, lidas.get(aba, []), self.cfg)
                self.hoteis_lidos_em = agora
            else:
                solicitacoes = self.solicitacoes
            status = {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in lidas.get(status_aba, []) if l}
            emails = [e for aba in self.abas_emails for e in espelho_emails.ler_aba(lidas.get(aba, []))]
            pedidos_caixa = {aba[len(espelho_emails.PREFIXO_PEDIDOS):]: espelho_emails.ler_pedidos(lidas.get(aba, []))
                             for aba in getattr(self, "abas_pedidos", []) if aba in lidas}
            if espelho_emails.ABA_EVENTOS in lidas:
                self.eventos_linhas = lidas[espelho_emails.ABA_EVENTOS]
            if ligacoes.ABA in lidas:
                with self.lock:
                    self.ligacoes_linhas = lidas[ligacoes.ABA]
                    self.ligacoes = ligacoes.dobrar(self.ligacoes_linhas)
            with self.lock:
                self.solicitacoes = solicitacoes
                self._aplicar_tratamento(trat, novas)
                self.emails = emails
                self.pedidos_caixa = pedidos_caixa
                self.status = status
                self.atualizado_em, self.erro = dados.agora(), ""
            self._montar_correio()
            try:
                self._lido_no_outlook()
            except Exception:
                logger.debug("lido no Outlook", exc_info=True)
            try:   # deixa a lista da tela pronta: quem abre o Painel não espera o cálculo (usuário, 11/10/2026)
                self.fila_da_tela(60)
            except Exception:
                logger.debug("lista pronta da tela", exc_info=True)
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler a planilha ({e})")
            self.erro = str(e)[:200]
            return
        try:
            self.envio_nf.tick(lidas, nome_do_agente())
        except Exception:
            logger.exception("fila de envio de NF")
        try:
            self._rede(lidas, solicitacoes)
        except Exception:
            logger.exception("rede de PCs")
        try:
            self._ligacoes_de_envios_falhos()
        except Exception:
            logger.exception("ligações de envios que falharam")
        try:
            self._avisar_urgencias()
        except Exception:
            logger.exception("aviso de urgência")

    def _juntar_tratamento(self, lidas, inteira):
        """-> (linhas da Tratamento com cabeçalho, só as novas | None = redobrar tudo).
        Leitura que falhou NUNCA vira aba vazia: sem a Tratamento, toda NF emitida pareceria pendente."""
        if lidas is None:
            if self.trat_linhas is None:
                raise RuntimeError("não consegui ler a aba Tratamento")
            return self.trat_linhas, []   # falhou nesta volta: fica o que já tinha
        if inteira:
            self.trat_lido_em = self.relogio()
            return (lidas or [dados.CABECALHO_TRATAMENTO]), None
        ultima = [str(v) for v in self.trat_linhas[-1]] if self.trat_linhas else []
        if lidas and [str(v) for v in lidas[0]] == ultima:
            return (self.trat_linhas + lidas[1:], lidas[1:]) if len(lidas) > 1 else (self.trat_linhas, [])
        # a última linha que eu conhecia mudou de lugar (faxina apagou linhas): relê inteira agora
        logger.info("🧹 A aba Tratamento mudou (faxina) — relendo inteira.")
        toda, erros = self.backend.ler_abas(self.central, [dados.ABA_TRATAMENTO])
        if dados.ABA_TRATAMENTO not in toda:
            raise RuntimeError(f"não consegui reler a aba Tratamento ({erros})")
        self.trat_lido_em = self.relogio()
        return (toda[dados.ABA_TRATAMENTO] or [dados.CABECALHO_TRATAMENTO]), None

    def _aplicar_tratamento(self, trat, novas):
        self.versao_dados = getattr(self, "versao_dados", 0) + 1   # a lista pronta da tela (fila_da_tela) vale até aqui
        """Chamado com self.lock. novas=None: redobra tudo; [] nada mudou; [...] só dobra as novas."""
        if novas is None or not self.estados:
            self.estados = dados.dobrar_eventos(trat)
        elif novas:
            dados.dobrar_eventos([dados.CABECALHO_TRATAMENTO] + novas, self.estados)
        self.trat_linhas = trat

    def _planilhas_sem_cadastro(self):
        if not e_principal(self.cfg):
            return []
        try:
            return json.load(open(PASTA_ESTADO / "planilhas_sem_cadastro.json", encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def relatorio_semana(self, deslocamento=0, tipo="semana"):
        """Relatório do dia ou da semana: Mail Analytics (só leitura) + pedidos de formulário do Painel."""
        dados_ma = relatorio_semana.ler(self.backend, self.cfg.get("mail_analytics_planilha", relatorio_semana.PLANILHA_MAIL_ANALYTICS))
        with self.lock:
            pedidos = [(s["data"], self.cadastro.dados(s["hotel"]).get("agente", "")) for s in self.solicitacoes if s.get("data")]
        rel = relatorio_semana.montar(dados_ma, datetime.date.today(), deslocamento, pedidos, tipo if tipo in ("dia", "mes") else "semana",
                                      self._contagem_fim_de_semana())
        self._ultimo_relatorio = rel
        return rel

    def _contagem_fim_de_semana(self):
        """Abas ContagemPainel_<PC> da Central (o fim de semana de João e Cristian contado pelo Painel), 10 min."""
        guardada = getattr(self, "_contagem_fds", None)
        if guardada and time.monotonic() - guardada[0] < 600:
            return guardada[1]
        try:
            abas = [a for a in self.backend.listar_abas(self.central) if a.startswith(contagem_painel.PREFIXO_ABA)]
            lidas = self.backend.ler_abas(self.central, abas)[0] if abas else {}
            dados_fds = contagem_painel.ler_abas(lidas.values())
        except Exception as e:
            logger.debug(f"contagem do fim de semana: {e}")
            dados_fds = guardada[1] if guardada else {}
        self._contagem_fds = (time.monotonic(), dados_fds)
        return dados_fds

    def cadastro_faltando(self):
        with self.lock:
            emails = [self.cadastro.dados(h).get("email", "") for h in self.cadastro.nomes()]
        faltam_planilhas = sorted({x for p in self.pcs() for x in p.get("saude", {}).get("cad", [])})
        return saude.cadastro_faltando(self.pcs(), emails, faltam_planilhas)

    def adicionar_cadastro(self, corpo, quem):
        """Cadastrar com um clique (usuário, 11/10/2026): acrescenta 1 linha [hotel, e-mail, agente] na aba
        Cadastro_Hoteis da Central. Não mexe em nenhuma planilha de hotel."""
        hotel = str(corpo.get("hotel", "")).strip().upper()
        email = str(corpo.get("email", "")).strip().lower()
        agente = str(corpo.get("agente", "")).strip()
        if not hotel or not agente or (email and "@" not in email):
            raise ValueError("preencha o hotel e o agente (e o e-mail da caixa, se tiver)")
        with self.lock:
            if self.cadastro.canonico(hotel):
                raise ValueError(f"{hotel} já está no cadastro")
        self.backend.anexar_linhas(self.central, self.cfg["aba_cadastro_hoteis"], [[hotel, email, agente]])
        logger.info(f"🏨 Cadastro_Hoteis: {hotel} ({email or 'sem caixa'}) → {agente} — por {quem}")
        self.abas_lidas_em = -1e9   # relê o cadastro na próxima volta
        return {"ok": True}

    LIDO_APLICADO = PASTA_ESTADO / "lido_aplicado.json"
    LIDO_OUTLOOK_DESDE = "2026-10-11T11:55:36"   # clique de antes desta regra não vai pro Outlook (era só o lido da equipe)

    def reler_tratamento(self):
        """Depois de gravar: só o fim da aba (o que acabou de entrar)."""
        inteira = self.trat_linhas is None
        faixas = {} if inteira else {dados.ABA_TRATAMENTO: f"A{len(self.trat_linhas)}:H"}
        lidas, _ = self.backend.ler_abas(self.central, [dados.ABA_TRATAMENTO], faixas=faixas)
        trat, novas = self._juntar_tratamento(lidas.get(dados.ABA_TRATAMENTO), inteira)
        with self.lock:
            self._aplicar_tratamento(trat, novas)

    def registrar(self, agente, pc, chave_sol, acao, valor=""):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada (a planilha pode ter mudado; atualize)")
        if acao == dados.ASSUMIR:
            self.reler_tratamento()
            dono = dados.quem_ganhou(self.estados, chave_sol)
            if dono and dono != agente:
                return {"ok": False, "motivo": f"Já está em tratamento por {dono}."}
        linha = dados.evento(dados.agora(), agente, pc, sol["aba"], sol["carimbo"], sol["email"], acao, valor)
        self.backend.anexar_linhas(self.central, dados.ABA_TRATAMENTO, [linha])
        self.reler_tratamento()
        if acao == dados.ASSUMIR:
            dono = dados.quem_ganhou(self.estados, chave_sol)
            if dono != agente:
                return {"ok": False, "motivo": f"{dono} assumiu um instante antes de você."}
        return {"ok": True}

    def fila(self, dias=None, desde=None):
        if dias:
            desde = (datetime.date.today() - datetime.timedelta(days=dias)).isoformat()
        try:
            controle = json.load(open(PASTA_ESTADO / "controle_nf.json", encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            controle = {}
        with self.lock:
            fila = dados.montar_fila(self.solicitacoes, self.estados, dados.nfs_do_controle(controle), desde)
        return hospedes.marcar(fila)   # hóspede único, pedido repetido e prazo (Etapa 2)

    def fila_da_tela(self, dias=None):
        """Pedidos pra tela. Notas fiscais = espelho da Caixa de Entrada (usuário, 11/10/2026): cada pedido cuja
        solicitação do robô está na Caixa de Entrada de algum PC vem com "na_caixa" (e entra mesmo se for antigo ou
        resolvido). Os outros continuam indo pra Visão geral e Gerência (resolvida some depois de 24 h)."""
        chave = (dias, getattr(self, "versao_dados", 0), id(getattr(self, "pedidos_caixa", None)),
                 datetime.datetime.now().strftime("%Y%m%d%H"))   # a hora entra: "resolvida há 24 h" muda com o relógio
        pronta = getattr(self, "_fila_pronta", None)
        if pronta and pronta[0] == chave:
            return pronta[1]
        limite = (datetime.datetime.now() - datetime.timedelta(hours=RESOLVIDA_HORAS)).isoformat(timespec="seconds")
        with self.lock:
            sols, caixas = list(self.solicitacoes), dict(getattr(self, "pedidos_caixa", {}) or {})
        na_caixa, sem_pedido = dados.ligar_caixa(sols, caixas)
        saida, vistos = [], set()
        for s in self.fila(dias):
            vistos.add(s["chave"])
            if s["chave"] in na_caixa:
                saida.append({**s, "na_caixa": na_caixa[s["chave"]]})
            elif not (s["situacao"] == dados.CONCLUIDA and not s["envio_pendente"] and dados.resolvida_em(s) < limite):
                saida.append(s)
        faltam = {k for k in na_caixa if k not in vistos}   # pedido antigo ainda na Caixa de Entrada
        if faltam:
            with self.lock:
                extra = dados.montar_fila([s for s in sols if s["chave"] in faltam], self.estados)
            saida += [{**s, "na_caixa": na_caixa[s["chave"]]} for s in hospedes.marcar(extra)]
        saida += sem_pedido
        self._fila_pronta = (chave, saida)
        return saida

    def resumo_caixa(self):
        """Que PCs já espelham as solicitações da Caixa de Entrada (versão nova) e quando atualizaram."""
        with self.lock:
            caixas = dict(getattr(self, "pedidos_caixa", {}) or {})
        saida = {}
        for p in self.pcs():
            linhas = caixas.get(p["pc"])
            saida[p["pc"]] = {"agente": p["agente"], "online": p["online"], "espelho": linhas is not None,
                              "emails": len(linhas or []), "atualizado": max((l["atualizado"] for l in linhas or []), default="")}
        return saida

    def salvar_cache(self, forcar=False):
        """Último estado em disco: depois de reiniciar o PC a janela já abre com dados."""
        if not self.atualizado_em or (not forcar and self.relogio() - self.cache_salvo < SALVAR_CACHE_SEGUNDOS):
            return
        with self.lock:
            dados_cache = {"versao": VERSAO_CACHE, "solicitacoes": self.solicitacoes, "estados": self.estados,
                           "status": self.status, "atualizado_em": self.atualizado_em, "fi": self.fi,
                           "cadastro": self.cadastro, "abas_hotel": self.abas_hotel}
        try:
            CAMINHO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            temporario = CAMINHO_CACHE.with_suffix(".tmp")
            temporario.write_bytes(pickle.dumps(dados_cache, protocol=pickle.HIGHEST_PROTOCOL))
            os.replace(temporario, CAMINHO_CACHE)
            self.cache_salvo = self.relogio()
        except OSError as e:
            logger.warning(f"⚠️ Não consegui salvar o cache do painel ({e})")

    def carregar_cache(self):
        try:
            c = pickle.loads(CAMINHO_CACHE.read_bytes())
        except (FileNotFoundError, OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
            return False
        if c.get("versao") != VERSAO_CACHE:
            return False
        self.solicitacoes, self.estados, self.status = c["solicitacoes"], c["estados"], c["status"]
        self.atualizado_em, self.fi, self.cadastro, self.abas_hotel = c["atualizado_em"], c["fi"], c["cadastro"], c["abas_hotel"]
        return True

    def atualizar_fi(self, forcar=False):
        """Fiscal Intelligence: o Mail Analytics grava 1x por dia, então reler a cada poucos minutos sobra."""
        if not self.fi_id or (not forcar and self.relogio() - self.fi_lido < self.fi_minutos * 60):
            return
        try:
            fi = fiscal_intelligence.ler(self.backend, self.fi_id, self.cadastro, self.desde, ignorar_hoteis=self.ignorar,
                                         lacunas_conhecidas=self.cfg.get("painel", {}).get("lacunas_conhecidas", {}),
                                         somam_fim_de_semana=self.cfg.get("painel", {}).get("somam_fim_de_semana"))
            with self.lock:
                self.fi, self.fi_erro = fi, ""
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler o Fiscal Intelligence ({e})")
            self.fi_erro = str(e)[:200]
        self.fi_lido = self.relogio()

    def atualizar_canceladas(self):
        """Arquivos (CANCELADA)/(SUBSTITUIDA) do Dropbox: a 1ª leitura dos PDFs leva minutos, então roda
        numa thread e as telas usam a última lista pronta."""
        if self.lendo_canceladas or self.relogio() - self.canceladas_lidas < CANCELADAS_MINUTOS * 60:
            return
        self.lendo_canceladas = True

        def ler():
            try:
                pastas = (self.cfg.get("dropbox_notas") or {}).get("pastas", [])
                cache = canceladas.ler_cache(CAMINHO_CANCELADAS)
                arquivos = canceladas.varrer(pastas, cache)
                canceladas.salvar_cache(CAMINHO_CANCELADAS, cache)
                with self.lock:
                    nomes, sols = list(self.cadastro.nomes()), list(self.solicitacoes)
                canceladas.atribuir_hoteis(arquivos, nomes, sols, self.cfg.get("apelidos_hoteis", {}),
                                           self.cfg.get("painel", {}).get("cnpj_hoteis", {}))
                with self.lock:
                    self.canceladas = arquivos
            except Exception:
                logger.exception("canceladas/substituídas do Dropbox")
            finally:
                self.canceladas_lidas, self.lendo_canceladas = self.relogio(), False

        threading.Thread(target=ler, daemon=True).start()

    def _periodo(self, ini, fim):
        hoje = datetime.date.today()
        ini = max(datetime.date.fromisoformat(ini) if ini else hoje.replace(day=1), self.desde)
        fim = min(datetime.date.fromisoformat(fim) if fim else hoje, hoje)
        return ini, max(fim, ini)

    def _ignorados(self):
        return {self.cadastro.canonico(h) or h for h in self.ignorar}

    def hoteis_por_agente(self):
        """[{hotel, agente}] do Cadastro_Hoteis (sem os ignorados): filtros de hotel e agente da caixa."""
        ign = self._ignorados()
        return [{"hotel": h, "agente": self.cadastro.dados(h).get("agente", ""),
                 "email": str(self.cadastro.dados(h).get("email", "")).strip().lower()}   # caixa do hotel (pastas dos e-mails)
                for h in self.cadastro.nomes() if h not in ign]

    def _fila_do_painel(self):
        ign = self._ignorados()
        return [s for s in self.fila(desde=self.desde.isoformat()) if s["hotel"] not in ign]

    def painel(self, ini, fim):
        ini, fim = self._periodo(ini, fim)
        hoje = datetime.date.today()
        fila = self._fila_do_painel()
        fi = self.fi or {"metricas": [], "fins_de_semana": {}, "saude": {}, "avisos": []}
        return {"ini": ini.isoformat(), "fim": fim.isoformat(), "desde": self.desde.isoformat(),
                "visao": metricas.visao_geral(fi["metricas"], fila, ini, fim, hoje, fi["fins_de_semana"], self.canceladas),
                "hoteis": metricas.tabela_hoteis(fi["metricas"], fila, ini, fim, hoje, self.cadastro, self._ignorados(),
                                                 self.canceladas),
                "saude": fi["saude"], "avisos": fi["avisos"], "fi_erro": self.fi_erro,
                "fi_lido_em": fi["lido_em"].isoformat(timespec="seconds") if fi.get("lido_em") else ""}

    def hotel(self, nome, ini, fim):
        ini, fim = self._periodo(ini, fim)
        fi = self.fi or {"metricas": [], "fins_de_semana": {}}
        return metricas.ficha_hotel(nome, fi["metricas"], self._fila_do_painel(), ini, fim,
                                    datetime.date.today(), fi["fins_de_semana"], self.cadastro, self.canceladas)

    def resumo_status(self):
        s = self.status
        return {"ligado": normalizar(s.get(STATUS_ROTULO_A1, "")) in ("true", "verdadeiro"),
                "ultima_execucao": s.get("Última execução com sucesso", ""),
                "resumo": s.get("Resumo da última execução", ""),
                "online": s.get("Robô online (último sinal)", ""),
                "comando": s.get("Comando", ""), "resposta": s.get("Resposta do robô", "")}


def admins_do_painel(cfg):
    return list((cfg.get("painel", {}) or {}).get("admins") or ["João"])


def operadores_deste_pc(cfg, liberado=False):
    """Operadores que este PC pode escolher (22/10/2026): o administrador (João) só no PC dele; nos outros PCs ele não
    aparece nem é aceito. liberado: modo casa e demonstração (só leitura / dados fictícios)."""
    todos = [k for k in cfg.get("agentes", {}) if not str(k).startswith("_")]
    if liberado or e_principal(cfg):
        return todos
    return [k for k in todos if k not in admins_do_painel(cfg)]


def e_admin_aqui(cfg, nome, liberado=False):
    """Só o João, e só no PC dele (os outros PCs não ganham as opções de admin trocando de usuário)."""
    return bool(liberado) or (nome in admins_do_painel(cfg) and e_principal(cfg))


def _cronometrado(metodo, verbo):
    """Embrulha do_GET/do_POST: registra quanto a resposta demorou (desempenho.py). Não muda nada do que o método faz."""
    def interno(self, *args, **kwargs):
        inicio = time.perf_counter()
        try:
            return metodo(self, *args, **kwargs)
        finally:
            desempenho.MEDIDOR.registrar(desempenho.rota_curta(getattr(self, "path", ""), verbo), time.perf_counter() - inicio,
                                         desempenho.LIMITE_HTTP_S, logger)
    return interno


def criar_handler(estado, cfg, token, ultimo_uso, envio=None):
    pc = socket.gethostname()
    hosts_ok = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
    envio = envio or Envio(ao_terminar=estado.atualizar)
    liberado = lambda: bool(getattr(estado, "so_ver", False) or getattr(estado, "demo", False))   # noqa: E731
    operadores = [k for k in cfg.get("agentes", {}) if not str(k).startswith("_")]
    # o que as rotas (rotas_api.py) enxergam do servidor; cada lambda procura o nome na hora, para os testes poderem trocá-lo
    contexto = SimpleNamespace(
        estado=estado, cfg=cfg, pc=pc, envio=envio, operadores=operadores, temas_ok=TEMAS_OK,
        agente=lambda: nome_do_agente(),
        marca_pagina=lambda: _marca_pagina(),
        e_admin=lambda: e_admin_aqui(estado.cfg, nome_do_agente(), liberado()),
        operadores_deste_pc=lambda recarregar=False: operadores_deste_pc(carregar_config() if recarregar else cfg, liberado()),
        ler_prefs=lambda: ler_prefs(),
        salvar_pref=lambda chave, valor: salvar_pref(chave, valor),
        carregar_config=lambda: carregar_config(),
        e_principal=lambda cfg_: e_principal(cfg_),
        escrever_linhas_status=lambda *a, **k: escrever_linhas_status(*a, **k),
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _json(self, corpo, codigo=200, comparar=False):
            dados_ = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
            versao = ""
            if comparar and codigo == 200:   # velocidade 3: a tela já tem isso = não manda de novo
                versao = assinatura_tela(corpo)
                if self.headers.get("X-Versao") == versao:   # só a hora da leitura e os PCs vão junto
                    junto = {k: corpo[k] for k in VOLATEIS_JUNTO if isinstance(corpo, dict) and k in corpo}
                    dados_ = json.dumps({"__igual": True, **junto}, ensure_ascii=False, default=str).encode("utf-8")
            dados_, gz = comprimir_se_vale(dados_, self.headers.get("Accept-Encoding"))
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            if versao:
                self.send_header("X-Versao", versao)
            if gz:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(dados_)))
            self.end_headers()
            self.wfile.write(dados_)

        def _autorizado(self):
            # Host fixo barra DNS rebinding; token barra POST vindo de outra página aberta no navegador
            return self.headers.get("Host") in hosts_ok and self.headers.get("X-Token") == token

        def do_GET(self):
            ultimo_uso[0] = time.monotonic()
            if self.headers.get("Host") not in hosts_ok:
                return self._json({"erro": "host"}, 403)
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                html = _pagina_inteira().replace("__TOKEN__", token).replace("__PAGINA__", _marca_pagina())
                corpo, gz = comprimir_se_vale(html.encode("utf-8"), self.headers.get("Accept-Encoding"))
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                if gz:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            selo = re.fullmatch(r"/assinaturas/([a-z0-9]+)\.png", url.path)
            if selo and envio_nf.caminho_selo(selo.group(1)):
                corpo = envio_nf.caminho_selo(selo.group(1)).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if url.path in ("/agentes/mapa", "/api/agentes", "/api/desempenho"):   # aba Agentes do Smith (28/10/2026): só o administrador, no PC dele
                if not e_admin_aqui(estado.cfg, nome_do_agente(), liberado()):
                    return self._json({"erro": "Só o administrador vê esta aba, no PC dele."}, 403)
                if url.path == "/api/agentes":
                    return self._json(agentes_smith.estado(estado.pcs()))
                if url.path == "/api/desempenho":   # quanto cada etapa do servidor demora (desempenho.py); só nomes e milissegundos
                    return self._json({"servidor": desempenho.MEDIDOR.resumo(), "versao": estado.versao})
                corpo, gz = comprimir_se_vale((PASTA_UI / "agentes" / "mapa.html").read_bytes(), self.headers.get("Accept-Encoding"))
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                if gz:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            estatico = ESTATICOS.get(url.path)
            if estatico:
                arquivo, tipo = estatico
                corpo = (PASTA_UI / arquivo).read_bytes()
                gz = False
                if tipo.startswith("text/"):   # imagem e fonte já são comprimidas
                    corpo, gz = comprimir_se_vale(corpo, self.headers.get("Accept-Encoding"))
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                if gz:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                self.send_header("Cache-Control", "max-age=31536000" if arquivo.startswith("fontes/") else "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            rota = rotas_api.GET.get(url.path)
            if rota is None:
                return self._json({"erro": "não encontrado"}, 404)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                return self._json(rota(contexto, q), comparar=url.path in rotas_api.COMPARAR)
            except KeyError as e:
                return self._json({"erro": str(e).strip("'\"")}, 404)
            except ValueError as e:
                return self._json({"erro": f"parâmetro inválido: {e}"}, 400)
            except Exception as e:
                logger.exception("erro na API")
                return self._json({"erro": f"não deu pra buscar agora: {e}"}, 500)

        def do_POST(self):
            ultimo_uso[0] = time.monotonic()
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            tamanho = int(self.headers.get("Content-Length") or 0)
            try:
                corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            except ValueError:
                return self._json({"erro": "JSON inválido"}, 400)
            path = urlparse(self.path).path
            if getattr(estado, "so_ver", False) and path not in rotas_api.POST_NO_MODO_CASA:
                return self._json({"ok": False, "motivo": "Modo casa: só visualização. Faça isso no PC do trabalho."})
            rota = rotas_api.POST.get(path)
            if rota is None:
                return self._json({"erro": "não encontrado"}, 404)
            try:
                resposta = rota(contexto, corpo)
                if isinstance(resposta, tuple):   # (corpo, código HTTP)
                    return self._json(*resposta)
                return self._json(resposta)
            except KeyError as e:
                return self._json({"ok": False, "motivo": str(e).strip("'\"")}, 409)
            except ValueError as e:
                return self._json({"ok": False, "motivo": str(e)}, 400)
            except Exception as e:
                logger.exception("erro na API")
                return self._json({"ok": False, "motivo": f"Erro ao gravar na planilha: {e}"}, 500)

    for verbo in ("do_GET", "do_POST"):   # tempo de cada resposta à tela (só a rota, sem o que vem depois do "?")
        setattr(Handler, verbo, _cronometrado(getattr(Handler, verbo), verbo[3:]))
    return Handler


def abrir_janela():
    """Abre o app (app_janela.py, pywebview). Sem pywebview instalado, cai pro Edge em modo aplicativo."""
    try:
        import webview  # noqa: F401
        pythonw = PASTA_PROJETO / ".venv" / "Scripts" / "pythonw.exe"
        subprocess.Popen([str(pythonw), str(PASTA_PROJETO / "src" / "app_janela.py")], cwd=str(PASTA_PROJETO))
        return
    except ImportError:
        pass
    edge = next((p for p in EDGE if os.path.exists(p)), None)
    url = f"http://127.0.0.1:{PORTA}/"
    if edge is None:
        import webbrowser
        return webbrowser.open(url)
    perfil = PASTA_ESTADO / "app_edge"   # perfil separado: a janela não se mistura com o Edge do usuário
    subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={perfil}", "--window-size=1440,900",
                      "--no-first-run", "--no-default-browser-check"])


def comprimir_se_vale(dados, aceita):
    """gzip só quando o navegador aceita e o corpo passa de 1 KB (auditoria 27/10/2026: /api/estado 1,8 MB -> 202 KB).
    -> (bytes, comprimido?)"""
    if len(dados) < 1024 or "gzip" not in (aceita or "").lower():
        return dados, False
    return gzip.compress(dados, compresslevel=4, mtime=0), True


def assinatura_tela(corpo):
    """Hash do que a tela mostra, sem o que muda sozinho a cada volta (VOLATEIS_TELA). Velocidade 3, 21/10/2026."""
    def limpar(x):
        if isinstance(x, dict):
            return {k: limpar(v) for k, v in x.items() if k not in VOLATEIS_TELA}
        if isinstance(x, list):
            return [limpar(v) for v in x]
        return x
    return hashlib.sha1(json.dumps(limpar(corpo), ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def esperar_proxima_volta(estado, ultimo_uso, em_uso, em_fundo, relogio=time.monotonic, dormir=time.sleep):
    """Espera a próxima leitura da Central: 15 s com a janela aberta, 1 min fechada. Novidade do robô (21/10/2026)
    adianta, com a janela aberta e pelo menos ACORDAR_MIN_SEGUNDOS depois da última leitura. Enquanto espera, olha a
    pasta de notas do Dropbox a cada 10 s. -> "tempo" | "novidade" """
    inicio = relogio()
    while True:
        aberta = relogio() - ultimo_uso[0] < JANELA_ABERTA_SEGUNDOS
        passou = relogio() - inicio
        if passou >= (em_uso if aberta else em_fundo):
            return "tempo"
        if aberta and estado.acordar.is_set() and passou >= ACORDAR_MIN_SEGUNDOS:
            return "novidade"
        try:
            estado.olhar_dropbox()
        except Exception:
            logger.debug("olhar o Dropbox", exc_info=True)
        dormir(1)


def porta_livre():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORTA)) != 0


def travar_instancia_unica():
    """Um servidor do Painel por PC (21/10/2026). Só olhar a porta deixava brecha: dois abertos quase juntos passavam os
    dois e, no Windows, os dois conseguem abrir a mesma porta. Dois Painéis vivos leem a mesma fila Envios_NF e podiam
    mandar o mesmo e-mail duas vezes. Mesma trava do robô e da janela.
    -> arquivo travado (manter aberto enquanto o processo vive) | None se já há outro."""
    import msvcrt
    os.makedirs(PASTA_ESTADO, exist_ok=True)
    arquivo = open(PASTA_ESTADO / "_painel.lock", "a+b")
    try:
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        return arquivo
    except OSError:
        arquivo.close()
        return None


_TRAVA = None   # fica aberta enquanto o Painel vive


def main():
    global _TRAVA
    sem_janela = "--sem-janela" in sys.argv
    limite = time.monotonic() + (10 if sem_janela else 0)   # religado logo após matar o anterior: porta e trava levam
    while True:                                              # uns segundos pra soltar
        _TRAVA = travar_instancia_unica() if porta_livre() else None
        if _TRAVA or time.monotonic() >= limite:
            break
        time.sleep(0.5)
    if not _TRAVA:
        if not sem_janela:
            abrir_janela()
        return 0

    from sheets import BackendGoogle
    cota_google.configurar("painel")
    modo_demo = "--demo" in sys.argv   # PC de casa: dados fictícios, sem Google/Outlook/chave (src/demo.py)
    cfg = carregar_config(exigir_chave=not modo_demo)
    so_ver = "--visualizar" in sys.argv and not modo_demo   # PC de casa com a chave: dados reais, só leitura
    if modo_demo:
        import demo
        global CAMINHO_CACHE
        CAMINHO_CACHE = PASTA_ESTADO / "painel_cache_demo.pkl"
        cfg = demo.configurar_cfg(cfg)
        backend_demo = demo.BackendDemo()
        estado = Estado(backend_demo, cfg)
        demo.preparar(estado, backend_demo)
        logger.info("🧪 MODO DEMONSTRAÇÃO: dados fictícios, nada vai pro Google nem pro Outlook")
    elif so_ver:
        from sheets import BackendSoLeitura
        CAMINHO_CACHE = PASTA_ESTADO / "painel_cache_casa.pkl"
        estado = Estado(BackendSoLeitura(caminho_chave_google(cfg)), cfg)
        logger.info("🏠 MODO CASA: dados reais, só visualização (não grava na Central, não mexe no Outlook)")
    else:
        estado = Estado(BackendGoogle(caminho_chave_google(cfg)), cfg)
    estado.demo = modo_demo
    estado.so_ver = so_ver
    if not modo_demo and estado.carregar_cache():
        logger.info(f"📦 Último estado carregado do disco ({estado.atualizado_em:%d/%m %H:%M}) — atualizando em seguida.")
    if not modo_demo and not so_ver:
        estado.segredo = rede_local.segredo_da_chave(caminho_chave_google(cfg))
        estado.rede_ligada = rede_local.Servidor(estado.segredo, {"buscar": estado.rede_buscar, "texto": estado.rede_texto,
                                                                  "anexo": estado.rede_anexo, "ping": estado.rede_ping,
                                                                  "enviar": estado.rede_enviar,
                                                                  "envio_nf": estado.rede_envio_nf,
                                                                  "novidade": estado.rede_novidade,
                                                                  "enviar_receber": estado.rede_enviar_receber,
                                                                  "caixas": estado.rede_caixas,
                                                                  "reiniciar_outlook": estado.rede_reiniciar_outlook,
                                                                  "conferir_envio": estado.rede_conferir_envio}).iniciar()
    token = secrets.token_urlsafe(24)
    ultimo_uso = [-1e9]
    estado.uso_ref = ultimo_uso
    servidor = ServidorPainel(("127.0.0.1", PORTA), criar_handler(estado, cfg, token, ultimo_uso))
    app = cfg.get("app", {})
    em_uso, em_fundo = int(app.get("atualizar_segundos", 15)), int(app.get("atualizar_segundos_fundo", 60))
    if so_ver:   # a cota do Google é dos 4 PCs do trabalho: em casa relê bem mais devagar
        em_uso, em_fundo = max(em_uso, 60), max(em_fundo, 300)

    def laco():
        """Fica rodando enquanto o PC estiver ligado. Janela aberta: relê rápido; fechada: devagar (cota da API)."""
        while True:
            estado.acordar.clear()   # novidade que chegar durante a leitura vale para a próxima volta
            medir = desempenho.MEDIDOR.medir   # só cronometra (28/10/2026): o que passa de 30 s vai para o log
            with medir("painel.volta_completa", logger=logger):
                with medir("painel.atualizar", logger=logger):
                    estado.atualizar()
                with medir("painel.notas_emails", logger=logger):
                    estado.atualizar_notas_emails()
                with medir("painel.fiscal_intelligence", logger=logger):
                    estado.atualizar_fi()
                with medir("painel.canceladas", logger=logger):
                    estado.atualizar_canceladas()
                with medir("painel.atividade", logger=logger):
                    try:
                        estado.atualizar_atividade()
                    except Exception as e:   # a tela de Monitoramento segue com o último valor guardado
                        logger.warning(f"⚠️ Não consegui ler a atividade da equipe ({str(e)[:100]})")
                with medir("painel.salvar_cache", logger=logger):
                    estado.salvar_cache()
            estado.versao_tela += 1
            esperar_proxima_volta(estado, ultimo_uso, em_uso, em_fundo)

    threading.Thread(target=laco, daemon=True).start()
    if not modo_demo and not so_ver:
        if not sem_outlook(cfg):   # PC só com o Painel não tem Outlook para vigiar nem para indexar
            estado.vigiar_caixa_de_saida()
            estado.iniciar_indice()
        estado.iniciar_nf_achadas()
    try:
        liberado = limpeza.aparar_registros(PASTA_LOGS)   # cópia girada antiga e grande (auditoria 27/10/2026)
        if liberado:
            logger.info(f"🧹 Registros antigos apagados: {liberado // 1_000_000} MB")
    except Exception as e:   # limpeza nunca derruba o Painel
        logger.warning(f"Limpeza de registros não rodou: {e}")
    logger.info(f"🖥️ Painel Notas Fiscais no ar em http://127.0.0.1:{PORTA}/ · agente {nome_do_agente()}")
    if not sem_janela:
        abrir_janela()
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
