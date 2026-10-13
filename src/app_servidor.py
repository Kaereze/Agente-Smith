"""Painel Notas Fiscais: servidor HTTP só em 127.0.0.1 + janela do Edge em modo aplicativo.

    python src\\app_servidor.py --sem-janela   servidor em segundo plano (tarefa SolicitacoesNF_Painel, no logon)
    python src\\app_servidor.py                abre a janela; liga o servidor antes se ele não estiver rodando

O servidor fica no ar enquanto o PC estiver ligado e mantém os dados atualizados, então a
janela abre já carregada. O último estado também vai pro disco (painel_cache.pkl) pra
sobreviver a um reinício. Todos os PCs leem e gravam a mesma Planilha Central.
"""
import datetime
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
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
import atividade
import atualizador
import avisos_windows
import busca_outlook
import canceladas
import correio
import hospedes
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
from arquivos import salvar_json
from hoteis import CadastroHoteis
from app_envio import Envio
from config import PASTA_ESTADO, PASTA_PROJETO, caminho_chave_google, carregar_config, e_principal
from log_util import configurar_logging
import outlook_vivo
from sheets import (LINHA_COMANDO, LINHA_PEDIDO, STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba)
from tratamento import normalizar

logger = configurar_logging("app")

PORTA = 8765
PASTA_UI = PASTA_PROJETO / "app_ui"
CAMINHO_PREFS = PASTA_ESTADO / "app.json"


def _marca_pagina():
    """Marca da versão da tela (data do arquivo mais novo em app_ui): mudou = a janela aberta recarrega sozinha
    (13/10/2026: a tela foi atualizada sem reiniciar o Painel e a janela continuava com a página antiga)."""
    try:
        return str(int(max(p.stat().st_mtime for p in PASTA_UI.iterdir() if p.suffix in (".html", ".js", ".css"))))
    except (OSError, ValueError):
        return ""


def _pagina_inteira(tentativas=6):
    """index.html lido inteiro: durante uma atualização o arquivo pode estar sendo regravado (lido pela metade = página quebrada)."""
    html = ""
    for _ in range(tentativas):
        html = (PASTA_UI / "index.html").read_text(encoding="utf-8", errors="replace")
        if html.rstrip().endswith("</html>"):
            return html
        time.sleep(0.25)
    return html
JANELA_ABERTA_SEGUNDOS = 90     # a janela pede dados a cada 15 s; sem pedido há 90 s = fechada
CAMINHO_CACHE = PASTA_ESTADO / "painel_cache.pkl"
CAMINHO_CANCELADAS = PASTA_ESTADO / "canceladas.json"
CANCELADAS_MINUTOS = 10
VERIFICAR_ATUALIZACAO_MINUTOS = 15
CAMINHO_VERSAO = PASTA_ESTADO / "versao_rodando.txt"
ATIVIDADE_CACHE_SEGUNDOS = 20
SALVAR_CACHE_SEGUNDOS = 120
VERSAO_CACHE = 1
NOTAS_EMAILS_SEGUNDOS = 120   # e-mail -> NF do Dropbox: recalculado a cada 2 min, fora da resposta da tela
# Leitura leve (08/10/2026): a cada 15 s o Painel baixava ~11 MB (abas dos hotéis + Tratamento inteira). Agora:
HOTEIS_SEGUNDOS = 120              # abas dos hotéis: só mudam com a cópia de 30 em 30 min -> relidas a cada 2 min
TRATAMENTO_COMPLETO_SEGUNDOS = 600 # Tratamento: a cada 15 s só as linhas novas; inteira a cada 10 min (garantia)
JANELA_PAINEL_DIAS = 120
TELAS = {"visao": "Visão geral", "fila": "Notas fiscais", "correio": "E-mails", "log": "Log", "maquinas": "Máquinas"}   # pra Máquinas mostrar onde cada um está
RESOLVIDA_HORAS = 24               # solicitação resolvida fica 24 h na lista e some (o Outlook/planilha guardam)
REINICIO_PENDENTE_MIN = 5          # código novo na pasta e o Painel ainda no velho por mais que isso: pede o reinício de novo
ESTATICOS = {   # lista fechada: nada fora daqui é servido do disco
    "/icone.png": ("icone.png", "image/png"),
    "/favicon.ico": ("icone.ico", "image/x-icon"),
    "/graficos.js": ("graficos.js", "text/javascript; charset=utf-8"),
    "/painel.js": ("painel.js", "text/javascript; charset=utf-8"),
    "/correio.js": ("correio.js", "text/javascript; charset=utf-8"),
    "/fontes/fontes.css": ("fontes/fontes.css", "text/css; charset=utf-8"),
}
ESTATICOS.update({f"/fontes/{f.name}": (f"fontes/{f.name}", "font/woff2") for f in (PASTA_UI / "fontes").glob("*.woff2")})
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


class Estado:
    """Cache em memória da Central. Uma leitura (batch) por atualização, pra caber na cota da API."""

    def __init__(self, backend, cfg, relogio=time.monotonic, servico_envio=None):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.envio_nf = servico_envio or envio_nf.ServicoEnvio(backend, cfg, socket.gethostname(), self.registrar_nf_enviada)
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
        self.abas_emails, self.emails = [], []
        self.avisos = avisos_windows.Avisos()
        self.notas_emails, self.notas_emails_em = {}, -1e9   # {id do e-mail: [NF do Dropbox]} — calculado em segundo plano
        self.trat_linhas, self.trat_lido_em, self.hoteis_lidos_em = None, -1e9, -1e9
        self.eventos_linhas, self.eventos_pendentes = [], []   # lido/não lido: gravados juntos, 1 escrita por volta
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
                             (atividade.ABA, atividade.CABECALHO), (rede_pcs.ABA_COMANDOS, rede_pcs.CAB_COMANDOS)):
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
                (list(abas) if ler_hoteis else [])
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

    # ---------- rede de PCs ----------
    def _extras_pc(self):
        """Colunas E-J da linha deste PC em PCs_Painel."""
        outlook = self.outlook or "?"
        leituras, escritas = cota_google.consumo_deste_pc()
        # "'" na frente: a planilha lê "09119e6" como número (9.12E+09) e estragaria a versão
        uso = getattr(self, "uso_ref", None)
        aberta = bool(uso and time.monotonic() - uso[0] < JANELA_ABERTA_SEGUNDOS)
        tela = TELAS.get(getattr(self, "vista_atual", ""), "")
        return [outlook, "'" + self.versao, self.cfg.get("papel", ""), rede_pcs.ultima_conferencia(),
                rede_local.endereco_deste_pc() if self.rede_ligada else "", f"'{leituras}/{escritas}",
                f"aberto|{tela}|{datetime.datetime.now():%H:%M}" if aberta else "fechado",
                saude.coluna(getattr(self, "saida_travada", 0), self._ultima_copia(), self._planilhas_sem_cadastro(),
                             self._ultimo_robo(), getattr(self, "ultimo_recebido", ""))]

    def _planilhas_sem_cadastro(self):
        if not e_principal(self.cfg):
            return []
        try:
            return json.load(open(PASTA_ESTADO / "planilhas_sem_cadastro.json", encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _ultimo_robo(self):
        """Quando o robô de envio (main.py, a cada 30 min no principal) terminou por último: aba Status (coluna B)."""
        if not e_principal(self.cfg):
            return ""
        q = str((self.status or {}).get("ultima_execucao", "")).strip()
        try:
            return datetime.datetime.strptime(q[:19], "%d/%m/%Y %H:%M:%S").isoformat(timespec="seconds")
        except ValueError:
            return ""

    def problemas_de_saude(self):
        """Faixa de saúde: o que os PCs publicam + o atraso do Mail Analytics (do relatório guardado)."""
        lista = saude.problemas(self.pcs())
        rel = getattr(self, "_ultimo_relatorio", None)
        if rel:
            lista += saude.mail_analytics_atrasado(rel.get("ultimo_dia"), datetime.date.today())
        return lista

    def relatorio_semana(self, deslocamento=0, tipo="semana"):
        """Relatório do dia ou da semana: Mail Analytics (só leitura) + pedidos de formulário do Painel."""
        dados_ma = relatorio_semana.ler(self.backend, self.cfg.get("mail_analytics_planilha", relatorio_semana.PLANILHA_MAIL_ANALYTICS))
        with self.lock:
            pedidos = [(s["data"], self.cadastro.dados(s["hotel"]).get("agente", "")) for s in self.solicitacoes if s.get("data")]
        rel = relatorio_semana.montar(dados_ma, datetime.date.today(), deslocamento, pedidos, "dia" if tipo == "dia" else "semana",
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

    def _ultima_copia(self):
        """Quando a cópia dos hotéis deu certo pela última vez (só o PC principal copia)."""
        if not e_principal(self.cfg):
            return ""
        try:
            return (PASTA_ESTADO / "ultima_copia.txt").read_text(encoding="utf-8").strip()[:19]
        except OSError:
            return ""

    def vigiar_caixa_de_saida(self):
        """A cada 2 min conta os e-mails parados há mais de 10 min na Caixa de Saída do Outlook deste PC (só lê)."""
        def rodar():
            import pythoncom
            pythoncom.CoInitialize()
            while True:
                try:
                    if not outlook_vivo.pode_usar():   # nunca cria um Outlook escondido; o guardião do conferente abre
                        time.sleep(120)
                        continue
                    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                    limite = datetime.datetime.now() - datetime.timedelta(minutes=saude.SAIDA_TRAVADA_MIN)
                    vistos, presos = set(), 0
                    self.ultimo_recebido = saude.ultimo_recebido(ns) or getattr(self, "ultimo_recebido", "")
                    for pasta in [ns.GetDefaultFolder(4)] + [c.DeliveryStore.GetDefaultFolder(4) for c in ns.Accounts]:
                        try:
                            if pasta.EntryID in vistos:
                                continue
                            vistos.add(pasta.EntryID)
                            for item in pasta.Items:
                                quando = item.LastModificationTime
                                if datetime.datetime(quando.year, quando.month, quando.day, quando.hour, quando.minute) < limite:
                                    presos += 1
                        except Exception:
                            continue
                    if presos and presos != getattr(self, "saida_travada", 0):
                        logger.warning(f"⚠️ Caixa de Saída do Outlook: {presos} e-mail(s) parado(s) há mais de "
                                       f"{saude.SAIDA_TRAVADA_MIN} min")
                    self.saida_travada = presos
                except Exception:
                    logger.debug("Caixa de Saída", exc_info=True)
                time.sleep(120)

        threading.Thread(target=rodar, daemon=True).start()

    def _conferencia_diaria(self, agente):
        """Teste diário automático (usuário, 11/10/2026): 1 vez por dia, depois das 8h, o PC principal confere a
        cópia dos hotéis, o robô de envio, a Caixa de Saída, o Outlook e o robô de cada PC, a versão e o Mail
        Analytics, e deixa o resultado no Log. Os mesmos problemas aparecem na hora na faixa de saúde."""
        hoje = datetime.date.today().isoformat()
        if not e_principal(self.cfg) or datetime.datetime.now().strftime("%H:%M") < "08:00" or                 getattr(self, "_conferido_em", "") == hoje:
            return []
        self._conferido_em = hoje
        try:
            self.relatorio_semana(0)   # lê o Mail Analytics (só leitura) pra saber se ele está em dia
        except Exception as e:
            logger.warning(f"⚠️ Conferência diária: não li a planilha do Mail Analytics ({e})")
        problemas = self.problemas_de_saude()
        if problemas:
            texto = f"conferência diária: {len(problemas)} problema(s) — " + " · ".join(p["texto"] for p in problemas)[:180]
            logger.warning(f"⚠️ Conferência diária: {len(problemas)} problema(s)")
            return [atividade.linha(atividade.FALHA, detalhe=texto, agente=agente)]
        logger.info("✅ Conferência diária: tudo funcionando")
        return [atividade.linha(atividade.ATUALIZADO, detalhe="conferência diária: tudo funcionando ✓ (cópia, envio, "
                                "Caixa de Saída, Outlook, robôs, versões e Mail Analytics)", agente=agente)]

    def _conferir_reinicio(self, agente):
        """O código na pasta mudou e este Painel ainda roda o velho (o reinício não aconteceu): depois de
        REINICIO_PENDENTE_MIN avisa no Log e pede o reinício de novo, 1 vez por versão (11/10/2026)."""
        if time.monotonic() < getattr(self, "_proximo_conferir_versao", 0):
            return []
        self._proximo_conferir_versao = time.monotonic() + 60
        na_pasta = envio_nf.versao_do_codigo()
        if not na_pasta or not self.versao or na_pasta.startswith(self.versao[:7]):
            self._versao_nova_desde = None
            return []
        desde = getattr(self, "_versao_nova_desde", None)
        if desde is None or desde[0] != na_pasta:
            self._versao_nova_desde = (na_pasta, time.monotonic(), False)
            return []
        if desde[2] or time.monotonic() - desde[1] < REINICIO_PENDENTE_MIN * 60:
            return []
        self._versao_nova_desde = (na_pasta, desde[1], True)
        logger.warning(f"⚠️ Código novo na pasta ({na_pasta}), mas este Painel ainda roda o {self.versao}: pedindo o reinício de novo")
        try:
            como = atualizador.pedir_reinicio()
        except Exception as e:
            como = f"o Agendador recusou ({str(e)[:80]})"
        return [atividade.linha(atividade.FALHA, detalhe=f"código {na_pasta} baixado, mas o PC continuava no {self.versao}: {como}",
                                agente=agente)]

    def _rede(self, lidas, solicitacoes):
        if getattr(self, "so_ver", False):   # modo casa: só olha; não executa comando nem se registra como PC
            return
        pc, agente = socket.gethostname(), nome_do_agente()
        linhas = []
        try:
            linhas += self._conferir_reinicio(agente)
        except Exception:
            logger.debug("conferir reinício", exc_info=True)
        try:
            linhas += self._conferencia_diaria(agente)
        except Exception:
            logger.debug("conferência diária", exc_info=True)
        if not self.versao_registrada:   # 1ª volta depois de ligar: registra se a versão mudou
            try:
                anterior = CAMINHO_VERSAO.read_text(encoding="utf-8").strip()
            except OSError:
                anterior = ""
            if anterior and anterior != self.versao:
                linhas.append(atividade.linha(atividade.ATUALIZADO, detalhe=f"de {anterior} para {self.versao}", agente=agente))
            CAMINHO_VERSAO.write_text(self.versao, encoding="utf-8")
            self.versao_registrada = True
        estado_outlook = rede_pcs.outlook_aberto()   # "aberto" | "sem janela" | "fechado" | None
        if estado_outlook is not None and estado_outlook != self.outlook:
            aberto = estado_outlook == "aberto"
            if self.outlook is not None or not aberto:
                tipo = atividade.OUTLOOK_ABERTO if aberto else atividade.OUTLOOK_FECHADO
                detalhe = ("o robô deste PC voltou a ler os e-mails das caixas daqui" if aberto else
                           "Outlook aberto sem janela: não baixa e-mail (o guardião vai abrir)" if estado_outlook == "sem janela"
                           else "o robô deste PC parou de ler os e-mails das caixas daqui")
                linhas.append(atividade.linha(tipo, detalhe=detalhe, agente=agente))
            self.outlook = estado_outlook
        # Pedido novo na planilha: só o principal registra (os outros veriam o mesmo e repetiriam)
        chaves = {s["chave"]: s for s in solicitacoes}
        if self.chaves_vistas is not None and e_principal(self.cfg):
            novas = [chaves[k] for k in chaves.keys() - self.chaves_vistas]
            linhas += [atividade.linha(atividade.NOVA_SOLICITACAO, s["hotel"], s["nome"],
                                       f"pedido de {s['carimbo']} · {s['email']}", agente="Robô") for s in novas[:30]]
            if len(novas) > 30:
                linhas.append(atividade.linha(atividade.NOVA_SOLICITACAO, detalhe=f"+{len(novas) - 30} pedidos novos", agente="Robô"))
        self.chaves_vistas = set(chaves)
        for id_c, comando, por in rede_pcs.pendentes(lidas.get(rede_pcs.ABA_COMANDOS, []), pc):
            if id_c not in self.comandos_em_execucao:
                self.comandos_em_execucao.add(id_c)
                threading.Thread(target=self._executar_comando, args=(id_c, comando, por), daemon=True).start()
        if self.cfg.get("painel", {}).get("atualizar_sozinho", True) and time.monotonic() >= self.proxima_verificacao:
            self.proxima_verificacao = time.monotonic() + VERIFICAR_ATUALIZACAO_MINUTOS * 60
            threading.Thread(target=self._verificar_atualizacao, args=(True,), daemon=True).start()
        atividade.registrar(self.backend, self.central, linhas)
        # Aviso do Windows: PC desligou, Outlook fechou ou conferência parou (principal: todos; os outros: só ele)
        for titulo, texto in self.avisos.mudancas(self.pcs(), pc, e_principal(self.cfg),
                                                  cfg_avisos=self.cfg.get("painel", {}).get("avisos")):
            avisos_windows.mostrar(titulo, texto)

    def _verificar_atualizacao(self, automatica, pedido_por=""):
        s = atualizador.situacao()
        motivo = atualizador.motivo_para_nao(s)
        self.atualizacao = {"verificado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                            "motivo": motivo, "atras": s["atras"]}
        if atualizador.pode_atualizar(s):
            quem = "automática" if automatica else f"pedida por {pedido_por}"
            ok, texto = atualizador.atualizar()
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO if ok else atividade.FALHA,
                detalhe=f"atualização {quem} ({s['atras']} commit(s) novo(s)): {texto}", agente=nome_do_agente())])
            return texto
        return motivo

    def _executar_comando(self, id_c, comando, por):
        try:
            texto = self._verificar_atualizacao(False, por) if comando == "atualizar" else "comando desconhecido"
        except Exception as e:
            texto = f"falhou: {e}"
        try:
            self.backend.anexar_linhas(self.central, rede_pcs.ABA_COMANDOS,
                                       [rede_pcs.resposta(id_c, socket.gethostname(), comando, texto or "ok")])
        except Exception as e:
            logger.warning(f"⚠️ Não consegui responder o comando {id_c} ({e})")

    def pedir_comando(self, para, comando, por):
        if comando not in rede_pcs.COMANDOS:
            raise ValueError("comando desconhecido")
        pcs = {p["pc"].lower() for p in rede_pcs.ler_pcs(self.envio_nf.pcs_linhas)}
        if para != "TODOS" and para.lower() not in pcs:
            raise ValueError("PC desconhecido")
        self.backend.anexar_linhas(self.central, rede_pcs.ABA_COMANDOS, [rede_pcs.pedido(para, comando, por)])
        return {"ok": True}

    def pcs(self):
        return rede_pcs.ler_pcs(self.envio_nf.pcs_linhas)

    def atividade_resumo(self):
        linhas, lido = self.atividade_cache
        if time.monotonic() - lido > ATIVIDADE_CACHE_SEGUNDOS:
            linhas = self.backend.ler_abas(self.central, [atividade.ABA])[0].get(atividade.ABA, [])
            self.atividade_cache = (linhas, time.monotonic())
        return {"pcs": self.pcs(), "eventos": atividade.ler(linhas, 400), "este_pc": socket.gethostname(),
                "versao": self.versao, "atualizacao": self.atualizacao}

    def registrar_nf_enviada(self, pedido, quem):
        """NF enviada pelo Painel: entra no pedido como emitida (todos os PCs veem). Resposta a um e-mail
        de quem não tem pedido pelo formulário não tem onde registrar."""
        if not pedido.get("aba"):
            return
        pc, quando = socket.gethostname(), dados.agora()
        linhas = [dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.NF, nf)
                  for nf in pedido.get("nfs", [])]
        linhas.append(dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.OBS,
                                   f"\"{pedido['assunto']}\" enviada ao hóspede ({pedido['para']}) pela caixa {pedido['conta_de']}"))
        self.backend.anexar_linhas(self.central, dados.ABA_TRATAMENTO, linhas)
        self.reler_tratamento()

    # ---------- aba E-mails ----------
    def _solicitacao_do_email(self, de):
        """Pedido do formulário mais recente desse mesmo e-mail (se houver). Índice por e-mail, refeito só quando
        a lista de pedidos muda: varrer 3,6 mil pedidos para cada e-mail deixava a tela lenta."""
        lista = self.solicitacoes
        if getattr(self, "_indice_emails", (None,))[0] is not lista:
            indice = {}
            for s in lista:
                for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                    atual = indice.get(x)
                    if atual is None or (s["data"], s["carimbo"]) > (atual["data"], atual["carimbo"]):
                        indice[x] = s
            self._indice_emails = (lista, indice)
        return self._indice_emails[1].get((de or "").lower())

    def _alertas_documento(self):
        """{e-mail do hóspede: alerta} das NFs que saíram pra outro CPF/CNPJ (pedidos dos últimos 45 dias)."""
        corte = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
        saida = {}
        with self.lock:
            sols, estados = list(self.solicitacoes), self.estados
        for s in sols:
            est = estados.get(s["chave"])
            if not est or not est["obs"] or (s["data"] and s["data"] < corte):
                continue
            urgentes, _ = dados.alertas_documento(est)
            if urgentes:
                for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                    saida[x] = f"NF {urgentes[0]['nf']}: {urgentes[0]['texto']}"
        return saida

    def _montar_correio(self):
        eventos = espelho_emails.dobrar_eventos(self.eventos_linhas + self.eventos_pendentes)
        entrada, enviados, _ = correio.juntar(self.emails, eventos, datetime.datetime.now(), self._alertas_documento())
        convs = correio.conversas(entrada)
        with self.lock:
            self.eventos_correio, self.entrada_correio, self.enviados_correio, self.convs = eventos, entrada, enviados, convs

    LIDO_APLICADO = PASTA_ESTADO / "lido_aplicado.json"
    LIDO_OUTLOOK_DESDE = "2026-10-11T11:55:36"   # clique de antes desta regra não vai pro Outlook (era só o lido da equipe)

    def _lido_no_outlook(self):
        """Abriu (ou "Não lido") no Painel -> o PC dono da caixa marca igual no Outlook dele (usuário, 11/10/2026).
        Cada PC só mexe nos e-mails das próprias caixas; cada clique é levado 1 vez só (lido_aplicado.json), até
        24 h depois (PC que estava desligado leva quando ligar). Só muda a marca de lido, nada mais no e-mail."""
        if getattr(self, "demo", False) or getattr(self, "so_ver", False) or getattr(self, "_lido_rodando", False) \
                or not outlook_vivo.pode_usar():
            return
        pc = socket.gethostname()
        if not hasattr(self, "_lido_aplicado"):
            try:
                self._lido_aplicado = json.load(open(self.LIDO_APLICADO, encoding="utf-8"))
            except (FileNotFoundError, ValueError):
                self._lido_aplicado = {}
        with self.lock:
            eventos = espelho_emails.dobrar_eventos(self.eventos_linhas + self.eventos_pendentes)
            meus = [e for e in self.emails if e["pc"] == pc and e["pasta"] == espelho_emails.ENTRADA]
        corte = max(self.LIDO_OUTLOOK_DESDE,
                    (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat(timespec="seconds"))
        tarefas = []
        for e in meus:
            ev = eventos.get(e["id"]) or {}
            q = ev.get("lido_mudou_em", "")
            if q and q >= corte and self._lido_aplicado.get(e["id"]) != q:
                tarefas.append((e["id"], bool(ev.get("lido")), q))
        if not tarefas:
            return
        self._lido_rodando = True

        def rodar():
            try:
                import pythoncom
                pythoncom.CoInitialize()
                ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                for i, lido, q in tarefas:
                    entry = espelho_emails.entry_do_email(i)
                    try:
                        if entry:
                            item = ns.GetItemFromID(entry)
                            if bool(item.UnRead) == lido:
                                item.UnRead = not lido
                                item.Save()
                                logger.info(f"📬 Outlook: marcado como {'lido' if lido else 'não lido'} (pedido pelo Painel) · "
                                            f"{str(item.Subject or '')[:60]}")
                    except Exception as erro:
                        logger.debug(f"lido no Outlook ({i}): {erro}")
                    self._lido_aplicado[i] = q
                corte_local = (datetime.datetime.now() - datetime.timedelta(hours=48)).isoformat(timespec="seconds")
                self._lido_aplicado = {k: v for k, v in self._lido_aplicado.items() if v >= corte_local}
                salvar_json(self.LIDO_APLICADO, self._lido_aplicado)
            except Exception:
                logger.exception("lido no Outlook")
            finally:
                self._lido_rodando = False

        threading.Thread(target=rodar, daemon=True).start()

    def _avisar_urgencias(self):
        """Aviso do Windows só quando um e-mail das caixas DESTE PC entra em Urgência (usuário, 08/10/2026)."""
        minhas = [c for c in self.convs if socket.gethostname() in c["pcs"]]
        novas, self.urgencias_avisadas = (correio.novas_urgencias(minhas, self.urgencias_avisadas or set())
                                          if self.urgencias_avisadas is not None else ([], {c["de"] for c in minhas if c["urgente"]}))
        cfg_av = {**avisos_windows.PADRAO, **(self.cfg.get("painel", {}).get("avisos") or {})}
        if not novas or not cfg_av["ativo"] or not (cfg_av["das"] <= datetime.datetime.now().strftime("%H:%M") < cfg_av["ate"]):
            return
        if len(novas) == 1:
            c = novas[0]
            motivo = (c["ultimo"].get("motivo_urgencia") or "urgência").lower()
            avisos_windows.mostrar("Urgência", f"{c['nome']} ({', '.join(c['hoteis'])}): {motivo}.")
        else:
            avisos_windows.mostrar("Urgência", f"{len(novas)} e-mails entraram em Urgência nas suas caixas.")

    def _pcs_por_nome(self):
        return {p["pc"]: p for p in self.pcs()}

    def lista_correio(self):
        """Caixa de Entrada, Urgência e Itens Enviados dos 4 PCs juntos (1 linha por hóspede)."""
        pcs = self._pcs_por_nome()
        with self.lock:
            convs, enviados = list(self.convs), list(self.enviados_correio)
        saida = []
        for c in convs:
            sol = self._solicitacao_do_email(c["de"])
            notas = [n for i in c["ids"] for n in self.notas_emails.get(i, [])]
            saida.append({**c, "notas": list({n.get("rel", n.get("nome")): n for n in notas}.values()),
                          "pcs_online": [pc for pc in c["pcs"] if pcs.get(pc, {}).get("online")],
                          "agentes": [pcs.get(pc, {}).get("agente", "") for pc in c["pcs"]],
                          "solicitacao": {"chave": sol["chave"], "hotel": sol["hotel"], "data": sol["data"]} if sol else None})
        espelhos = {}
        for e in self.emails:   # quando cada PC atualizou o espelho por último (PC desligado = espelho parado)
            espelhos[e["pc"]] = max(espelhos.get(e["pc"], ""), e["atualizado"])
        with self.lock:
            entrada = list(getattr(self, "entrada_correio", []))
        por_de = {c["de"]: c for c in saida}
        emails = [{**e, "pc_online": bool(pcs.get(e["pc"], {}).get("online")), "agente": pcs.get(e["pc"], {}).get("agente", ""),
                   "total_conversa": por_de.get(e["de"], {}).get("total", 1),
                   "prazo": por_de.get(e["de"], {}).get("prazo"),
                   "notas": self.notas_emails.get(e["id"], []),
                   "solicitacao": por_de.get(e["de"], {}).get("solicitacao")} for e in entrada]
        return {"conversas": saida, "emails": emails, "enviados": enviados, "contagem": correio.contagem(convs),
                "pcs": [{"pc": p["pc"], "agente": p["agente"], "online": p["online"], "espelho": espelhos.get(p["pc"], ""),
                         "rede": bool(p.get("rede"))} for p in pcs.values()],
                "este_pc": socket.gethostname()}

    def lista_emails(self):
        """Compatibilidade (tela antiga): e-mails da entrada, 1 por linha."""
        return [{**e, "recebido": e["quando"]} for e in getattr(self, "entrada_correio", [])]

    def atualizar_notas_emails(self, forcar=False):
        """NF do Dropbox de cada e-mail espelhado (lê o Dropbox e às vezes o PDF: segundos). Roda no laço de fundo
        a cada NOTAS_EMAILS_SEGUNDOS; a lista de e-mails só consulta o resultado e responde na hora."""
        if not forcar and self.relogio() - self.notas_emails_em < NOTAS_EMAILS_SEGUNDOS:
            return
        self.notas_emails_em = self.relogio()
        mapa = {}
        for e in list(self.emails):
            if e["pasta"] != espelho_emails.ENTRADA:
                continue
            try:
                local = espelho_emails.item_local(e["id"]) if e["pc"] == socket.gethostname() else {}
                mapa[e["id"]] = envio_nf.notas_do_email({**e, "texto": local.get("texto") or e.get("previa", "")}, self.cfg)
            except Exception as erro:
                logger.debug(f"NF do Dropbox pro e-mail {e['id']}: {erro}")
        self.notas_emails = mapa

    def _email(self, id_email):
        e = next((x for x in self.emails if x["id"] == id_email and x["pasta"] != espelho_emails.RESPOSTA), None)
        if e is None:
            raise KeyError("e-mail não está mais na lista (pode ter sido respondido ou excluído)")
        return e

    def _caixas_de_hotel(self):
        """{caixa: hotel} de todos os hotéis do cadastro (a busca/leitura pela rede só abre essas caixas)."""
        saida = {}
        for h in self.cadastro.nomes():
            caixa = str(self.cadastro.dados(h).get("email", "")).strip().lower()
            if "@" in caixa:
                saida[caixa] = saida.get(caixa, "") + (" / " if caixa in saida else "") + h
        return saida

    def _enderecos_rede(self, so_online=True):
        return {p["pc"]: p["rede"] for p in self.pcs() if p.get("rede") and (p["online"] or not so_online)
                and p["pc"] != socket.gethostname()}

    # --- chamadas que chegam dos outros PCs (rede_local) ---
    def rede_buscar(self, corpo):
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        r = busca_outlook.buscar(ns, self._caixas_de_hotel(), corpo.get("q", ""), socket.gethostname(),
                                 limite=min(int(corpo.get("limite") or busca_outlook.LIMITE_POR_PC), 200))
        return {**r, "pc": socket.gethostname()}

    def rede_texto(self, corpo):
        """Texto inteiro de um e-mail das caixas deste PC: do espelho (já lido) ou direto do Outlook."""
        local = espelho_emails.item_local(str(corpo.get("id", ""))) if corpo.get("id") else {}
        if local and "texto" in local:
            return {"texto": local.get("texto", ""), "citado": local.get("citado", ""), "pc": socket.gethostname()}
        if not corpo.get("entry"):
            raise KeyError("e-mail não está mais no espelho deste PC")
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        return busca_outlook.abrir(ns, str(corpo["entry"]), self._caixas_de_hotel(), socket.gethostname())

    def rede_ping(self, _corpo):
        return {"pc": socket.gethostname(), "agente": nome_do_agente(), "versao": self.versao}

    # --- o que a tela pede ---
    def texto_email(self, id_email="", pc="", entry=""):
        """Texto inteiro, pedido ao vivo pro PC dono (nada fica guardado aqui). PC dono desligado: a cópia da
        aba CorreioTexto_<PC> (só existe enquanto o e-mail está sem resposta)."""
        if id_email and not pc:
            pc = self._email(id_email)["pc"]
        if pc == socket.gethostname():
            return {**self.rede_texto({"id": id_email, "entry": entry}), "origem": "este PC"}
        endereco = self._enderecos_rede().get(pc)
        if endereco and self.segredo:
            r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "texto", {"id": id_email, "entry": entry}).get(pc, {})
            if "erro" not in r:
                return {**r, "origem": "ao vivo"}
        if not id_email:
            raise KeyError(f"o PC {pc} não respondeu pela rede agora — tente de novo em instantes")
        return {**self._texto_da_planilha(pc, id_email), "origem": "cópia (PC dono sem rede)"}

    def _texto_da_planilha(self, pc, id_email):
        e = self._email(id_email)
        versao, textos = self.textos_cache.get(pc, ("", {}))
        if versao != e.get("versao_texto") or id_email not in textos:
            aba = espelho_emails.nome_aba_textos(pc)
            textos = espelho_emails.ler_textos(self.backend.ler_abas(self.central, [aba])[0].get(aba, []))
            self.textos_cache[pc] = (e.get("versao_texto"), textos)
        texto, citado = textos.get(id_email, ("", ""))
        return {"texto": texto or e.get("previa", ""), "citado": citado, "pc": pc}

    def buscar_outlook(self, termo):
        """Pergunta aos Outlooks dos PCs ligados (este incluído) ao mesmo tempo. -> resultados + quem respondeu."""
        termo = busca_outlook.limpar_termo(termo)
        if len(termo) < 3:
            return {"resultados": [], "pcs": {}, "termo": termo}
        respostas = {}
        enderecos = self._enderecos_rede()
        import threading as _t
        local = {}
        fio = _t.Thread(target=lambda: local.update(r=self._buscar_local(termo)))
        fio.start()
        if enderecos and self.segredo:
            respostas = rede_local.perguntar_a_todos(self.segredo, enderecos, "buscar", {"q": termo})
        fio.join(busca_outlook.TEMPO_MAXIMO + 3)
        respostas[socket.gethostname()] = local.get("r", {"erro": "o Outlook deste PC não respondeu a tempo"})
        pcs = self._pcs_por_nome()
        for p in pcs.values():
            if p["pc"] not in respostas:
                respostas[p["pc"]] = {"erro": "desligado" if not p["online"] else "sem endereço de rede (atualize o Painel dele)"}
        resultados = [r for resp in respostas.values() for r in resp.get("resultados", [])]
        resultados.sort(key=lambda r: r["quando"], reverse=True)
        situacao = {pc: ({"ok": True, "achados": len(r.get("resultados", [])), "completo": r.get("completo", True)}
                         if "erro" not in r else {"ok": False, "erro": r["erro"]}) for pc, r in respostas.items()}
        return {"resultados": resultados, "pcs": situacao, "termo": termo,
                "agentes": {p["pc"]: p["agente"] for p in pcs.values()}}

    def _buscar_local(self, termo):
        try:
            return self.rede_buscar({"q": termo})
        except Exception as e:
            return {"erro": f"Outlook deste PC: {e}"}

    def _hospedes(self):
        """Hóspede único (e-mail ou CPF/CNPJ): {endereço: [pedidos do mesmo hóspede]}. Refeito só quando a lista de
        pedidos muda (como o índice por e-mail)."""
        lista = self.solicitacoes
        if getattr(self, "_indice_hospedes", (None,))[0] is not lista:
            grupo = hospedes.grupos(lista)
            membros, por_endereco = {}, {}
            for s in lista:
                membros.setdefault(grupo[s["chave"]], []).append(s)
            for s in lista:
                for x in hospedes.enderecos(s):
                    por_endereco.setdefault(x, set()).add(grupo[s["chave"]])
            self._indice_hospedes = (lista, {x: [s for g in gs for s in membros[g]] for x, gs in por_endereco.items()})
        return self._indice_hospedes[1]

    def conversa(self, de):
        """Tudo do hóspede na tela: e-mails sem resposta (todos os PCs), o que saiu pra ele nas últimas 24 h, os
        pedidos do formulário dele e as NFs já enviadas (pelo registro, conferido no PDF pelo robô).
        Hóspede único (Etapa 2): entram também os pedidos feitos com outro e-mail e o mesmo CPF/CNPJ."""
        de = (de or "").strip().lower()
        pedidos = self._hospedes().get(de, [])
        ligados = sorted({x for s in pedidos for x in hospedes.enderecos(s)} - {de})[:5]
        with self.lock:
            recebidos = [e for e in getattr(self, "entrada_correio", []) if e["de"] == de]
            enviados = [e for e in self.enviados_correio if de in [x.strip() for x in e["para"].split(",")]]
            fila = [s for s in dados.montar_fila(pedidos, self.estados)]
        pcs = self._pcs_por_nome()
        linha_do_tempo = ([{"tipo": "recebido", **e} for e in recebidos] + [{"tipo": "enviado", **e} for e in enviados] +
                          [{"tipo": "formulario", "quando": s["data"], "chave": s["chave"], "hotel": s["hotel"],
                            "nome": s["nome"], "situacao": s["situacao"], "nfs": s["nfs"], "envios": s["envios"],
                            "email": s["email"], "alerta_doc": s["alerta_doc"]}
                           for s in fila])
        linha_do_tempo.sort(key=lambda x: x["quando"], reverse=True)
        nfs_enviadas = [{"nfs": env["nfs"], "para": env["para"], "quando": env["quando"], "hotel": s["hotel"]}
                        for s in fila for env in s["envios"]]
        return {"de": de, "nome": next((e["nome"] for e in recebidos if e["nome"]), fila[0]["nome"] if fila else de),
                "linha_do_tempo": linha_do_tempo, "nfs_enviadas": nfs_enviadas, "enderecos": ligados,
                "pcs": {pc: {"online": p["online"], "agente": p["agente"]} for pc, p in pcs.items()}}

    def evento_correio(self, ids, acao, agente):
        """Lido / não lido (equipe toda). Gravado junto com os outros na próxima volta (1 escrita só)."""
        if acao not in ("LIDO", "NAO_LIDO"):
            raise ValueError("ação desconhecida")
        pc = socket.gethostname()
        with self.lock:
            na_tela = {x["id"]: x["lido"] for x in getattr(self, "entrada_correio", [])}   # o que aparece (vem do Outlook)
            for i in ids[:200]:
                atual = na_tela.get(i, self.eventos_correio.get(i, {}).get("lido", False))
                if atual != (acao == "LIDO"):
                    self.eventos_pendentes.append(espelho_emails.evento(str(i), acao, agente, pc))
        self._montar_correio()
        try:   # e-mail das caixas deste PC: já marca no Outlook (sem esperar a próxima volta)
            self._lido_no_outlook()
        except Exception:
            logger.debug("lido no Outlook", exc_info=True)
        return {"ok": True}

    def _gravar_eventos_pendentes(self):
        with self.lock:
            pendentes, self.eventos_pendentes = self.eventos_pendentes, []
        if not pendentes:
            return
        try:
            self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, pendentes)
            self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + pendentes
        except Exception as e:
            logger.warning(f"⚠️ Não consegui gravar lido/não lido ({e}) — tento na próxima volta")
            with self.lock:
                self.eventos_pendentes = pendentes + self.eventos_pendentes

    def excluir_email(self, id_email, agente):
        """Some na hora pra equipe toda; o PC dono move pra Itens Excluídos do Outlook dele (o "Desfazer" de 10 s
        fica na tela: só depois dele o pedido chega aqui)."""
        e = self._email(id_email)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.EXCLUIR)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "EXCLUIR", agente)
        self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, [linha])
        self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + [linha]
        self._montar_correio()
        return r

    def encaminhar_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        para = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("para", ""))) if "@" in x)
        if not para:
            raise ValueError("preencha pra quem encaminhar")
        assunto = e["assunto"] if e["assunto"].lower().startswith(("enc:", "fw:", "fwd:")) else "ENC: " + e["assunto"]
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        return self.envio_nf.pedir(sol, para, assunto, e["caixa"], [], quem, str(corpo.get("corpo", "")),
                                   responder=e["id"], acao=envio_nf.ENCAMINHAR)

    def opcoes_email(self, id_email):
        e = self._email(id_email)
        destino, motivo = self.envio_nf.destino_para(e["caixa"], aceitar_desligado=True)
        sol = self._solicitacao_do_email(e["de"])
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg) if sol else []
        if not sugestoes:   # e-mail sem formulário (ex.: recepção repassando o pedido): a NF achada pelo nº/nome
            sugestoes = envio_nf.notas_do_email(e, self.cfg)
        assunto = e["assunto"] if e["assunto"].lower().startswith(("re:", "res:")) else "RE: " + e["assunto"]
        return {"para": [e["de"]], "conta_de": e["caixa"], "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": e["nome"] or e["de"], "hotel": e["hotel"], "assunto": assunto, "corpo": "",
                "corpo_nf": envio_nf.mensagem_padrao(self.cfg), "assinatura": "", "assinatura_com_mensagem": False,
                "selos": envio_nf.selos(), "selo": envio_nf.selo_do_agente(nome_do_agente()), "email": e,
                "solicitacao": sol["chave"] if sol else ""}

    def contas_de_hotel(self):
        """Caixas notafiscal@ dos 4 PCs -> [{"conta", "hotel", "agente", "pc", "destino"}], as deste PC primeiro.
        É o "De" do Novo e-mail (usuário, 13/10/2026): sai pela caixa do hotel, pelo Outlook do PC dono."""
        hotel_da_conta = {}
        for h in self.cadastro.nomes():
            email = str(self.cadastro.dados(h).get("email", "")).strip().lower()
            if email:
                hotel_da_conta[email] = h
        este = socket.gethostname()
        vistas, saida = set(), []
        for p in sorted(self.pcs(), key=lambda x: x["pc"] != este):
            for c in p.get("contas_lista", []):
                if c.startswith("notafiscal@") and c not in vistas:
                    vistas.add(c)
                    saida.append({"conta": c, "hotel": hotel_da_conta.get(c, saude.nome_da_caixa(c)),
                                  "agente": p.get("agente", ""), "pc": p["pc"], "online": bool(p.get("online"))})
        return saida

    def opcoes_email_novo(self, conta=""):
        """Opções do Novo e-mail: escolher a caixa do hotel, escrever para quem quiser (modelo: solicitação de dados)."""
        contas = self.contas_de_hotel()
        if not contas:
            raise KeyError("nenhuma caixa de hotel nos PCs da equipe (aba PCs_Painel)")
        escolhida = next((c for c in contas if c["conta"] == conta.lower()), contas[0])
        destino, motivo = self.envio_nf.destino_para(escolhida["conta"], aceitar_desligado=True)
        return {"novo": True, "para": [], "conta_de": escolhida["conta"], "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "contas": contas,
                "sugestoes": [], "nome": "", "hotel": escolhida["hotel"], "assunto": "", "corpo": "",
                "corpo_nf": "", "assinatura": "", "assinatura_com_mensagem": False, "selos": envio_nf.selos(),
                "selo": envio_nf.selo_do_agente(nome_do_agente())}

    def enviar_email_novo(self, corpo, quem):
        """Novo e-mail ao hóspede: sai da caixa do hotel escolhida, sem ligar a nenhuma solicitação (não marca NF)."""
        conta = str(corpo.get("conta_de", "")).strip().lower()
        contas = {c["conta"]: c for c in self.contas_de_hotel()}
        if conta not in contas:
            raise ValueError("escolha a caixa do hotel de onde o e-mail sai")
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        texto = str(corpo.get("corpo", "")).strip()
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        if not texto:
            raise ValueError("escreva a mensagem")
        import base64
        anexos = [{"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "anexo.pdf")),
                   "conteudo": base64.b64decode(a.get("b64", ""))}
                  for a in corpo.get("anexos") or [] if a.get("tipo") == "arquivo"]
        cc = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in x)
        selo = str(corpo.get("selo") or "")
        sol = {"aba": "", "carimbo": "", "email": para, "hotel": contas[conta]["hotel"], "nome": para}
        logger.info(f"✉️ Novo e-mail de {conta} para {para}: \"{assunto}\" — por {quem}")
        return self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, str(corpo.get("corpo", "")), cc,
                                   selo if envio_nf.caminho_selo(selo) else "", livre=True)

    def responder_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        sol = self._solicitacao_do_email(e["de"]) or {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"],
                                                       "nome": e["nome"] or e["de"]}
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        import base64
        anexos = []
        for a in corpo.get("anexos") or []:
            if a.get("tipo") == "arquivo":
                anexos.append({"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "nota.pdf")),
                               "conteudo": base64.b64decode(a.get("b64", ""))})
            elif a.get("tipo") == "dropbox" and a.get("rel"):
                anexos.append({"tipo": "dropbox", "rel": a["rel"], "nome": a.get("nome", "")})
        if not anexos and not str(corpo.get("corpo", "")).strip():
            raise ValueError("escreva a resposta ou anexe a nota")
        cc = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in x)
        selo = str(corpo.get("selo") or "")
        return self.envio_nf.pedir(sol, para, assunto, e["caixa"], anexos, quem, str(corpo.get("corpo", "")), cc,
                                   selo if envio_nf.caminho_selo(selo) else "", responder=e["id"])

    def opcoes_envio(self, chave_sol):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        conta = self.cadastro.dados(sol["hotel"]).get("email", "")
        destino, motivo = self.envio_nf.destino_para(conta, aceitar_desligado=True)
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg)
        try:
            assinatura = envio_nf.assinatura_previa(conta, nome_do_agente())
        except Exception:
            logger.exception("prévia da assinatura")
            assinatura = ""
        com_mensagem = envio_nf.assinatura_tem_mensagem(assinatura)
        selos = envio_nf.selos()
        return {"para": envio_nf.destinatarios(sol), "conta_de": conta, "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": sol["nome"], "hotel": sol["hotel"],
                "corpo": envio_nf.mensagem_padrao(self.cfg) if selos or not com_mensagem else "",
                "assinatura": assinatura, "assinatura_com_mensagem": com_mensagem and not selos,
                "selos": selos, "selo": envio_nf.selo_do_agente(nome_do_agente())}

    def pedir_envio(self, corpo, quem):
        sol = next((s for s in self.solicitacoes if s["chave"] == corpo.get("chave")), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        conta = (corpo.get("conta_de") or self.cadastro.dados(sol["hotel"]).get("email", "")).strip().lower()
        import base64
        anexos = []
        for a in corpo.get("anexos") or []:
            if a.get("tipo") == "arquivo":
                anexos.append({"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "nota.pdf")),
                               "conteudo": base64.b64decode(a.get("b64", ""))})
            elif a.get("tipo") == "dropbox" and a.get("rel"):
                anexos.append({"tipo": "dropbox", "rel": a["rel"], "nome": a.get("nome", "")})
        if not anexos:
            raise ValueError("anexe a nota fiscal")
        cc = ";".join(e.strip() for e in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in e)
        selo = str(corpo.get("selo") or "")
        return self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, corpo.get("corpo"), cc,
                                   selo if envio_nf.caminho_selo(selo) else "")

    def conferir_anexos(self, corpo):
        """Antes de enviar (usuário, 11/10/2026): abre cada PDF anexado e confere com o pedido (CPF/CNPJ, valor, nome,
        datas — a mesma regra do robô). -> {"avisos": [texto], "conferidas": n}. Só lê; não envia nada."""
        import base64
        import io
        import types
        from controle_nf import conferir_conteudo, documento_diferente, provas_da_solicitacao
        sol = next((s for s in self.solicitacoes if s["chave"] == corpo.get("chave")), None) if corpo.get("chave") else None
        if sol is None and corpo.get("id"):
            e = next((x for x in self.emails if x["id"] == corpo.get("id")), None)
            sol = self._solicitacao_do_email(e["de"]) if e else None
        if sol is None:
            return {"avisos": [], "conferidas": 0, "sem_pedido": True}
        provas = {**provas_da_solicitacao(types.SimpleNamespace(campos=sol.get("campos", []))), "nomes": sol.get("nomes", [])}
        raiz = envio_nf.raiz_dropbox(self.cfg)
        avisos, conferidas = [], 0
        for a in corpo.get("anexos") or []:
            nome = os.path.basename(str(a.get("nome") or a.get("rel") or "nota.pdf"))
            if not nome.lower().endswith(".pdf"):
                continue
            texto = ""
            try:
                from pypdf import PdfReader
                if a.get("tipo") == "arquivo":
                    leitor = PdfReader(io.BytesIO(base64.b64decode(a.get("b64", ""))))
                    texto = "\n".join((p.extract_text() or "") for p in leitor.pages[:3])
                elif a.get("tipo") == "dropbox" and a.get("rel"):
                    caminho = os.path.join(str(raiz), a["rel"]) if raiz else a["rel"]
                    from arquivos import so_na_nuvem
                    if os.path.exists(caminho) and not so_na_nuvem(caminho):   # só na nuvem: não baixa (regra do usuário)
                        texto = envio_nf._texto_da_nota_rapido(caminho, os.path.getmtime(caminho))
            except Exception as erro:
                logger.debug(f"conferir anexo {nome}: {erro}")
            resultado, prova = conferir_conteudo(provas, texto)
            if resultado == "sem_texto":
                continue   # PDF escaneado: não dá pra conferir aqui (o robô confere depois com OCR)
            conferidas += 1
            diferente = documento_diferente(provas, texto)
            if resultado == "nao_confere":
                avisos.append(f"{nome}: não parece ser a nota deste pedido ({prova})")
            elif diferente.startswith("⚠"):
                avisos.append(f"{nome}: {diferente[2:]}")
        return {"avisos": avisos, "conferidas": conferidas, "pedido": sol.get("nome", "")}

    def situacao_envio(self, id_envio):
        local = self.envio_nf.locais.get(id_envio)
        if local and local["estado"] != "enviando":
            return local
        fresca = envio_nf.dobrar_fila(self.backend.ler_abas(self.central, [envio_nf.ABA_FILA])[0].get(envio_nf.ABA_FILA, [[]]))
        return self.envio_nf.situacao(id_envio, fresca)

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
        return [{"hotel": h, "agente": self.cadastro.dados(h).get("agente", "")} for h in self.cadastro.nomes() if h not in ign]

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


def criar_handler(estado, cfg, token, ultimo_uso, envio=None):
    pc = socket.gethostname()
    hosts_ok = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
    envio = envio or Envio(ao_terminar=estado.atualizar)
    operadores = [k for k in cfg.get("agentes", {}) if not str(k).startswith("_")]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _json(self, corpo, codigo=200):
            dados_ = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
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
                corpo = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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
            estatico = ESTATICOS.get(url.path)
            if estatico:
                arquivo, tipo = estatico
                corpo = (PASTA_UI / arquivo).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Cache-Control", "max-age=31536000" if arquivo.startswith("fontes/") else "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            if url.path == "/api/estado":
                dias = int(parse_qs(url.query).get("dias", ["45"])[0] or 0)
                estado.vista_atual = parse_qs(url.query).get("vista", [""])[0]
                return self._json({
                    "agente": nome_do_agente(), "pc": pc, "erro": estado.erro, "operadores": operadores,
                    "atualizado_em": estado.atualizado_em.isoformat(timespec="seconds") if estado.atualizado_em else "",
                    "atualizar_segundos": int(cfg.get("app", {}).get("atualizar_segundos", 15)),
                    "status": estado.resumo_status(), "fila": estado.fila_da_tela(dias), "pcs": estado.pcs(),
                    "caixa_pcs": estado.resumo_caixa(), "saude": estado.problemas_de_saude(),
                    "hoteis": estado.hoteis_por_agente(), "demo": bool(getattr(estado, "demo", False)), "pagina": _marca_pagina(), "so_ver": bool(getattr(estado, "so_ver", False)),
                    "tema": ler_prefs().get("tema", ""), "professor": ler_prefs().get("professor", True),
                })
            if url.path == "/api/envio":
                def ler_status():
                    aba = cfg["aba_status"]
                    linhas = estado.backend.ler_abas(estado.central, [aba])[0].get(aba, [])
                    return {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in linhas if l}
                return self._json(envio.situacao(ler_status))
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/api/envio_nf/opcoes":
                    return self._json(estado.opcoes_envio(q.get("chave", "")))
                if url.path == "/api/envio_nf/status":
                    return self._json(estado.situacao_envio(q.get("id", "")))
                if url.path == "/api/painel":
                    return self._json(estado.painel(q.get("ini"), q.get("fim")))
                if url.path == "/api/hotel":
                    return self._json(estado.hotel(q.get("nome", ""), q.get("ini"), q.get("fim")))
                if url.path == "/api/relatorio_semana":
                    try:
                        q = parse_qs(url.query)
                        return self._json(estado.relatorio_semana(int(q.get("deslocamento", q.get("semana", ["0"]))[0] or 0),
                                                                  q.get("tipo", ["semana"])[0]))
                    except Exception as e:
                        logger.warning(f"⚠️ Relatório da semana: {e}")
                        return self._json({"erro": f"não consegui ler a planilha do Mail Analytics ({str(e)[:120]})"})
                if url.path == "/api/cadastro/faltando":
                    return self._json({"faltando": estado.cadastro_faltando(),
                                       "agentes": sorted({p["agente"] for p in estado.pcs() if p.get("agente")})})
                if url.path == "/api/atividade":
                    return self._json(estado.atividade_resumo())
                if url.path == "/api/emails":
                    return self._json({"emails": estado.lista_emails(), "este_pc": pc})
                if url.path == "/api/correio":
                    return self._json(estado.lista_correio())
                if url.path == "/api/correio/conversa":
                    return self._json(estado.conversa(q.get("de", "")))
                if url.path == "/api/correio/texto":
                    return self._json(estado.texto_email(q.get("id", ""), q.get("pc", ""), q.get("entry", "")))
                if url.path == "/api/correio/buscar":
                    return self._json(estado.buscar_outlook(q.get("q", "")))
                if url.path == "/api/email/opcoes":
                    return self._json(estado.opcoes_email(q.get("id", "")))
                if url.path == "/api/email/novo":
                    return self._json(estado.opcoes_email_novo(q.get("conta", "")))
            except KeyError as e:
                return self._json({"erro": str(e).strip("'\"")}, 404)
            except ValueError as e:
                return self._json({"erro": f"parâmetro inválido: {e}"}, 400)
            except Exception as e:
                logger.exception("erro na API")
                return self._json({"erro": f"não deu pra buscar agora: {e}"}, 500)
            return self._json({"erro": "não encontrado"}, 404)

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
            if getattr(estado, "so_ver", False) and path not in ("/api/professor", "/api/agente", "/api/atualizar"):
                return self._json({"ok": False, "motivo": "Modo casa: só visualização. Faça isso no PC do trabalho."})
            try:
                if path == "/api/acao":
                    r = estado.registrar(nome_do_agente(), pc, corpo["chave"], corpo["acao"], corpo.get("valor", ""))
                    return self._json(r)
                if path == "/api/professor":   # modo professor (dicas na tela) ligado/desligado, por PC
                    salvar_pref("professor", bool(corpo.get("ligado")))
                    return self._json({"ok": True})
                if path == "/api/tema":   # tema por PC (claro, escuro ou o do Windows), lembrado depois de reiniciar
                    tema = str(corpo.get("tema", ""))
                    if tema not in TEMAS_OK:
                        return self._json({"ok": False, "motivo": "tema desconhecido"}, 400)
                    salvar_pref("tema", tema)
                    return self._json({"ok": True})
                if path == "/api/agente":
                    nome = str(corpo.get("nome", "")).strip()[:40]
                    if nome not in operadores:
                        return self._json({"ok": False, "motivo": "operador desconhecido"}, 400)
                    salvar_pref("agente", nome)
                    return self._json({"ok": True})
                if path == "/api/enviar":
                    if e_principal(carregar_config()):   # aqui mesmo: rápido e com log direto da memória
                        if not envio.iniciar_local(nome_do_agente()):
                            return self._json({"ok": False, "motivo": "Já tem um envio em andamento."})
                        return self._json({"ok": True, "modo": "local"})
                    quando = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
                    escrever_linhas_status(estado.backend, cfg, {LINHA_COMANDO: "ENVIAR",
                                                                 LINHA_PEDIDO: f"{nome_do_agente()} (Painel) | {quando}"})
                    envio.iniciar_remoto()
                    return self._json({"ok": True, "modo": "remoto"})
                if path == "/api/envio_nf":
                    return self._json(estado.pedir_envio(corpo, nome_do_agente()))
                if path == "/api/cadastro/adicionar":
                    return self._json(estado.adicionar_cadastro(corpo, nome_do_agente()))
                if path == "/api/envio_nf/conferir":
                    return self._json(estado.conferir_anexos(corpo))
                if path == "/api/email/responder":
                    return self._json(estado.responder_email(corpo, nome_do_agente()))
                if path == "/api/email/novo":
                    return self._json(estado.enviar_email_novo(corpo, nome_do_agente()))
                if path == "/api/correio/evento":
                    return self._json(estado.evento_correio([str(i) for i in corpo.get("ids", [])], str(corpo.get("acao", "")),
                                                            nome_do_agente()))
                if path == "/api/correio/excluir":
                    return self._json(estado.excluir_email(str(corpo.get("id", "")), nome_do_agente()))
                if path == "/api/correio/encaminhar":
                    return self._json(estado.encaminhar_email(corpo, nome_do_agente()))
                if path == "/api/comando":
                    return self._json(estado.pedir_comando(str(corpo.get("para", "")), str(corpo.get("comando", "")),
                                                           f"{nome_do_agente()} ({pc})"))
                if path == "/api/atualizar":
                    estado.atualizar()
                    estado.atualizar_fi(forcar=True)
                    return self._json({"ok": not estado.erro, "motivo": estado.erro})
            except KeyError as e:
                return self._json({"ok": False, "motivo": str(e).strip("'\"")}, 409)
            except ValueError as e:
                return self._json({"ok": False, "motivo": str(e)}, 400)
            except Exception as e:
                logger.exception("erro na API")
                return self._json({"ok": False, "motivo": f"Erro ao gravar na planilha: {e}"}, 500)
            return self._json({"erro": "não encontrado"}, 404)

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


def porta_livre():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORTA)) != 0


def main():
    sem_janela = "--sem-janela" in sys.argv
    if sem_janela:   # religado logo após matar o anterior: a porta pode levar uns segundos pra soltar
        limite = time.monotonic() + 10
        while not porta_livre() and time.monotonic() < limite:
            time.sleep(0.5)
    if not porta_livre():
        if not sem_janela:
            abrir_janela()
        return 0

    from sheets import BackendGoogle
    import cota_google
    cota_google.configurar("painel")
    cfg = carregar_config()
    modo_demo = "--demo" in sys.argv   # PC de casa: dados fictícios, sem Google/Outlook/chave (src/demo.py)
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
                                                                  "ping": estado.rede_ping}).iniciar()
    token = secrets.token_urlsafe(24)
    ultimo_uso = [-1e9]
    estado.uso_ref = ultimo_uso
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), criar_handler(estado, cfg, token, ultimo_uso))
    app = cfg.get("app", {})
    em_uso, em_fundo = int(app.get("atualizar_segundos", 15)), int(app.get("atualizar_segundos_fundo", 60))
    if so_ver:   # a cota do Google é dos 4 PCs do trabalho: em casa relê bem mais devagar
        em_uso, em_fundo = max(em_uso, 60), max(em_fundo, 300)

    def laco():
        """Fica rodando enquanto o PC estiver ligado. Janela aberta: relê rápido; fechada: devagar (cota da API)."""
        while True:
            estado.atualizar()
            estado.atualizar_notas_emails()
            estado.atualizar_fi()
            estado.atualizar_canceladas()
            estado.salvar_cache()
            inicio = time.monotonic()
            while True:
                aberta = time.monotonic() - ultimo_uso[0] < JANELA_ABERTA_SEGUNDOS
                if time.monotonic() - inicio >= (em_uso if aberta else em_fundo):
                    break
                time.sleep(1)

    threading.Thread(target=laco, daemon=True).start()
    if not modo_demo and not so_ver:
        estado.vigiar_caixa_de_saida()
    logger.info(f"🖥️ Painel Notas Fiscais no ar em http://127.0.0.1:{PORTA}/ · agente {nome_do_agente()}")
    if not sem_janela:
        abrir_janela()
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
