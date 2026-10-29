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
import indice_emails
import ligacoes
import cota_google
import envio_nf
import enviar_receber
import nf_achadas
import nf_cobre
import espelho_emails
import envio_pc_dono
import rede_local
import rede_pcs
import contagem_painel
import relatorio_semana
import saude
import fiscal_intelligence
import painel_metricas as metricas
import agentes_smith
import desempenho
from arquivos import salvar_json
from hoteis import CadastroHoteis
from app_envio import Envio
from config import PASTA_ESTADO, PASTA_LOGS, PASTA_PROJETO, caminho_chave_google, carregar_config, e_principal
import limpeza
from log_util import configurar_logging
import outlook_vivo
from sheets import (LINHA_COMANDO, LINHA_PEDIDO, STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba,
                    nome_intervalo)
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
JANELA_ABERTA_SEGUNDOS = 90     # a janela pede dados a cada 15 s; sem pedido há 90 s = fechada
CAMINHO_CACHE = PASTA_ESTADO / "painel_cache.pkl"
CAMINHO_CANCELADAS = PASTA_ESTADO / "canceladas.json"
CANCELADAS_MINUTOS = 10
VERIFICAR_ATUALIZACAO_MINUTOS = 15
SEM_REDE_SEGUNDOS = 300      # PC que não respondeu pela rede: 5 min usando a cópia, sem esperar
CAMINHO_VERSAO = PASTA_ESTADO / "versao_rodando.txt"
ATIVIDADE_CACHE_SEGUNDOS = 20
SALVAR_CACHE_SEGUNDOS = 120
VERSAO_CACHE = 1
NOTAS_EMAILS_SEGUNDOS = 120   # e-mail -> NF do Dropbox: recalculado a cada 2 min, fora da resposta da tela
VOLATEIS_TELA = {"atualizado_em", "visto", "dias"}   # mudam sozinhos a cada volta: fora da comparação do "igual"
VOLATEIS_JUNTO = ("atualizado_em", "pcs")            # ... e estes vão junto com o {"__igual"} (cabeçalho em dia)
ACORDAR_MIN_SEGUNDOS = 12     # novidade do robô relê na hora, mas no máximo 1 vez a cada 12 s (cota do Google: 7/min)
DROPBOX_OLHAR_SEGUNDOS = 10   # pasta de notas do Dropbox: mudou = NF nova, refaz a lista e as NFs dos e-mails já
ENVIADOS_RAPIDO_SEGUNDOS = 1.0   # consulta rápida nos Itens Enviados do Outlook quando o índice ainda não tem o envio do hóspede
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


class Estado:
    """Cache em memória da Central. Uma leitura (batch) por atualização, pra caber na cota da API."""

    def __init__(self, backend, cfg, relogio=time.monotonic, servico_envio=None):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.envio_nf = servico_envio or envio_nf.ServicoEnvio(backend, cfg, socket.gethostname(), self.registrar_nf_enviada)
        self.envio_nf.segundo_plano = lambda trabalho: threading.Thread(target=trabalho, daemon=True, name="envio_nf").start()   # noqa: E731
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
                             self._ultimo_robo(), getattr(self, "ultimo_recebido", ""), getattr(self, "motivo_outlook", ""),
                             getattr(self, "caixas_senha", []))]

    def _planilhas_sem_cadastro(self):
        if not e_principal(self.cfg):
            return []
        try:
            return json.load(open(PASTA_ESTADO / "planilhas_sem_cadastro.json", encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _ultimo_robo(self):
        """Quando o robô de envio (main.py, a cada 10 min no principal) terminou por último: aba Status (coluna B)."""
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
        lista += saude.pedidos_sem_envio(list(getattr(self, "solicitacoes", []) or []))   # pedido parado (15/10/2026)
        rel = getattr(self, "_ultimo_relatorio", None)
        if rel:
            lista += saude.mail_analytics_atrasado(rel.get("ultimo_dia"), datetime.date.today())
        return lista

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

    def _ultima_copia(self):
        """Quando a cópia dos hotéis deu certo pela última vez (só o PC principal copia)."""
        if not e_principal(self.cfg):
            return ""
        try:
            return (PASTA_ESTADO / "ultima_copia.txt").read_text(encoding="utf-8").strip()[:19]
        except OSError:
            return ""

    def iniciar_indice(self):
        """Índice local dos e-mails deste PC (pesquisa instantânea, 20/10/2026): monta aos poucos numa linha de fundo."""
        try:
            self.indice = indice_emails.Indice()
        except Exception as e:
            logger.warning(f"⚠️ Índice de e-mails não abriu ({e}) — a pesquisa continua direto no Outlook")
            return
        self.montador = indice_emails.Montador(self.indice)

        def rodar():
            import pythoncom
            pythoncom.CoInitialize()
            while True:
                pausa = 120
                try:
                    if outlook_vivo.pode_usar():   # nunca cria um Outlook escondido; o guardião do conferente abre
                        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                        pausa = self.montador.passo(ns, self._caixas_de_hotel())
                except Exception as e:
                    logger.debug(f"índice de e-mails: {e}")
                    pausa = 60
                time.sleep(pausa)
        threading.Thread(target=rodar, daemon=True, name="indice_emails").start()

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
                    try:   # por que o Outlook parou (26/10/2026): Trabalhar Offline, janela de senha, certificado
                        self.motivo_outlook = saude.motivo_outlook(ns)
                        self.caixas_senha = saude.caixas_pedindo_senha() if self.motivo_outlook == "senha" else []
                    except Exception:
                        self.motivo_outlook = ""
                        self.caixas_senha = []
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
                    try:
                        self.caixas_presas = saude.presos_por_conta(ns)   # por conta, pro botão "caixas com problema"
                    except Exception:
                        self.caixas_presas = []
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
        for titulo, texto in self.avisos.outlook(self.pcs(), pc, e_principal(self.cfg)):   # Outlook parado (26/10/2026)
            avisos_windows.mostrar(titulo, texto)

    def _verificar_atualizacao(self, automatica, pedido_por=""):
        s = atualizador.situacao(so_etiquetadas=automatica)   # automática: só versão com etiqueta (canal de teste, 27/10/2026)
        motivo = atualizador.motivo_para_nao(s)
        self.atualizacao = {"verificado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                            "motivo": motivo, "atras": s["atras"]}
        if atualizador.pode_atualizar(s):
            quem = "automática" if automatica else f"pedida por {pedido_por}"
            na_pasta_antes = envio_nf.versao_do_codigo()
            ok, texto, reiniciou = atualizador.atualizar(so_etiquetadas=automatica)
            if ok and not reiniciou:   # só documentação: o código que roda é o mesmo da versão nova
                self._adotar_versao_sem_reiniciar(na_pasta_antes)
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO if ok else atividade.FALHA,
                detalhe=f"atualização {quem} ({s['atras']} commit(s) novo(s)): {texto}", agente=nome_do_agente())])
            return texto
        na_pasta = envio_nf.versao_do_codigo()
        if not automatica and atualizador.precisa_reiniciar(s, self.versao, na_pasta):   # pedido: só reinicia
            como = atualizador.so_reiniciar()
            texto = f"código {na_pasta[:7]} já estava na pasta, o Painel rodava {self.versao.split(' ')[0]}: {como}"
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO, detalhe=f"atualização pedida por {pedido_por}: {texto}", agente=nome_do_agente())])
            return texto
        return motivo

    def _adotar_versao_sem_reiniciar(self, na_pasta_antes):
        """Atualização só de documentação (21/10/2026): passa a valer a versão nova sem reiniciar, pra a faixa de saúde
        e o _conferir_reinicio não pedirem reinício. Só se este Painel já rodava o código da pasta: com um reinício
        pendente de antes (código novo baixado e não reiniciado), fica como está e o _conferir_reinicio cuida."""
        nova = envio_nf.versao_do_codigo()
        if not nova or not na_pasta_antes or not self.versao or not na_pasta_antes.startswith(self.versao[:7]):
            return
        self.versao = nova
        try:
            CAMINHO_VERSAO.write_text(nova, encoding="utf-8")
        except OSError:
            logger.debug("versao_rodando.txt", exc_info=True)

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

    def atualizar_atividade(self, forcar=False):
        """Lê a aba Atividade_Robo do Google e guarda na memória. Chamado pelo laço do Painel, NUNCA pelo clique da tela."""
        _, lido = self.atividade_cache
        if not forcar and time.monotonic() - lido < ATIVIDADE_CACHE_SEGUNDOS:
            return
        linhas = self.backend.ler_abas(self.central, [atividade.ABA])[0].get(atividade.ABA, [])
        self.atividade_cache = (linhas, time.monotonic())

    def atividade_resumo(self):
        linhas, _ = self.atividade_cache   # só memória: o clique nunca espera o Google (29/10/2026); quem lê é o laço
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

    def _notas_do_pedido(self, sol, nfs):
        """Textos dos PDFs (índice das pastas do Dropbox) das NF já ligadas ao pedido: [(nº, nome do arquivo, texto)].
        O CPF/CNPJ da nota tem que ser o do pedido: a numeração das notas se repete entre hotéis."""
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return []
        docs = set(nf_achadas._alvo(sol)["documentos"])
        return [(e.get("nf"), e.get("nome", ""), e.get("texto", "")) for _c, e in indice.itens()
                if e.get("nf") in nfs and not e.get("sem_texto") and (not docs or e.get("doc") in docs)]

    def _pedidos_com_nf_por_email(self):
        """{e-mail do hóspede: (pedido, [nº das NF])} dos pedidos dos últimos 45 dias que já têm NF."""
        corte = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
        with self.lock:
            sols, estados = list(self.solicitacoes), self.estados
        mapa = {}
        for s in sols:
            nfs = [str(n) for n in (estados.get(s["chave"]) or {}).get("nfs", [])]
            if not nfs or (s.get("data") or "") < corte:
                continue
            for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                if x not in mapa or (s["data"], s["carimbo"]) > (mapa[x][0]["data"], mapa[x][0]["carimbo"]):
                    mapa[x] = (s, nfs)
        return mapa

    def _alertas_nova_nota(self):
        """{e-mail do hóspede: "Pede nova nota (NF 2186): ..."} — o e-mail novo pede algo (datas, serviço, CPF/CNPJ,
        descrição) que a NF já enviada não cobre (27/10/2026). Só marca urgência; nada é movido nem apagado. Aqui lê só a prévia
        do e-mail (a tela confere o texto inteiro ao abrir)."""
        mapa = self._pedidos_com_nf_por_email()
        if not mapa or getattr(self, "nf_indice", None) is None:
            return {}
        saida, vistos = {}, {}
        with self.lock:
            emails = list(self.emails)
        for r in emails:
            de = (r.get("de") or "").lower()
            if r["pasta"] != espelho_emails.ENTRADA or {"formulario", "aviso"} & set(r.get("classes", [])) or de not in mapa:
                continue
            if r["quando"] <= vistos.get(r["de"], ""):
                continue
            sol, nfs = mapa[de]
            textos = [t for _n, _p, t in self._notas_do_pedido(sol, nfs)]
            if not textos:
                continue
            vistos[r["de"]] = r["quando"]
            motivo = nf_cobre.motivo_curto(nf_cobre.analisar(r.get("previa", ""), textos), nfs)
            if motivo:
                saida[r["de"]] = motivo
            else:
                saida.pop(r["de"], None)
        return saida

    def _textos_do_hospede(self, e):
        """Texto novo + citado de TODOS os e-mails do hóspede na lista (o histórico inteiro), do mais velho ao mais novo."""
        cache = self.__dict__.setdefault("_textos_email", {})
        textos = []
        irmaos = sorted((x for x in list(self.emails) if x["pasta"] == espelho_emails.ENTRADA
                         and (x.get("de") or "").lower() == (e.get("de") or "").lower()), key=lambda x: x["quando"])
        for x in irmaos:
            if x["id"] not in cache:
                try:
                    t = self.texto_email(x["id"])
                    cache[x["id"]] = (t.get("texto", ""), t.get("citado", ""))
                except Exception:
                    cache[x["id"]] = (x.get("previa", ""), "")
            textos += list(cache[x["id"]])
        return textos

    def nf_cobre(self, id_email):
        """Caixa "NF" do e-mail aberto (27/10/2026): (1) a NF já enviada x o que o hóspede pede agora; (2) o HISTÓRICO INTEIRO do
        hóspede (todas as mensagens, com a parte citada) x as notas prontas nas pastas, achadas pelo CPF/CNPJ."""
        e = self._email(id_email)
        saida = {"nfs": []}
        achado = self._pedidos_com_nf_por_email().get((e.get("de") or "").lower())
        nfs = []
        if achado:
            sol, nfs = achado
            try:
                texto = self.texto_email(id_email).get("texto", "") or e.get("previa", "")
            except Exception:
                texto = e.get("previa", "")
            notas = self._notas_do_pedido(sol, nfs)
            analise = nf_cobre.analisar(texto, [t for _n, _p, t in notas])
            enviados = list(self.enviados_correio)
            sem = nf_achadas.sem_envio_confirmado(nfs, enviados, envio_nf.destinatarios(sol)) if enviados else []
            saida = {**analise, "nfs": [{"nf": n, "pdf": next((p for nn, p, _t in notas if nn == n), "")} for n in nfs],
                     "avisos_envio": sem, "sugere_concluir": analise["cobre"] is True and not sem,
                     "motivo_urgencia": nf_cobre.motivo_curto(analise, nfs)}
        indice = getattr(self, "nf_indice", None)
        if indice is not None:
            try:
                textos = self._textos_do_hospede(e)
                docs = set()
                for t in textos:
                    docs |= nf_achadas.documentos_do_texto(t)
                sol = achado[0] if achado else self._solicitacao_do_email(e["de"])
                if sol:
                    docs |= set(nf_achadas._alvo(sol)["documentos"])
                prontas = nf_achadas.notas_por_documento(indice, docs, raiz=envio_nf.raiz_dropbox(self.cfg), ja_ligadas=nfs, com_texto=True) if docs else []
                itens = nf_cobre.pedido_do_historico(textos)
                if prontas and itens:
                    saida["prontas"] = [{"nf": n["nf"], "pdf": n["nome"]} for n in prontas]
                    saida["historico"] = nf_cobre.comparar_historico(itens, [{"nf": n["nf"], "texto": n["texto"]} for n in prontas])
            except Exception:
                logger.exception("histórico do hóspede x notas prontas")
        return saida

    def mover_email_nf(self, id_email, agente):
        """Botão direito > "Tirar da caixa de entrada" (27/10/2026): ESTE e-mail, mesmo já respondido, vai para a pasta
        "NF enviada" da caixa do hotel, no Outlook do PC dono. A Caixa de Entrada é só dos que ainda esperam resposta.
        Nada é apagado; sempre um clique da pessoa (com "Desfazer" de 10 s na tela)."""
        e = self._email(id_email)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.MOVER_NF)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "EXCLUIR", agente)   # some da entrada pra equipe toda, na hora
        self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, [linha])
        self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + [linha]
        self._montar_correio()
        logger.info(f"📁 Tirar da entrada: e-mail de {e['de']} indo para \"{envio_nf.PASTA_NF_ENVIADA}\" (pedido de {agente})")
        return r

    def concluir_conversa(self, id_email, agente):
        """Botão Concluir (27/10/2026): move a conversa inteira do hóspede (os e-mails dele na entrada) para a pasta "NF enviada"
        da caixa do hotel, no Outlook do PC dono. Sempre um clique da pessoa; nada é apagado."""
        e0 = self._email(id_email)
        conversa = [x for x in self.entrada_correio if x["de"] == e0["de"]] or [e0]
        linhas, feitos, falhas = [], 0, set()
        for e in conversa:
            sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
            r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.MOVER_NF)
            if r.get("ok"):
                feitos += 1
                linhas.append(espelho_emails.evento(e["id"], "EXCLUIR", agente))   # some da entrada pra equipe toda, na hora
            else:
                falhas.add(str(r.get("motivo", ""))[:120])
        if linhas:
            self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, linhas)
            self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + linhas
            self._montar_correio()
        logger.info(f"📁 Concluir: {feitos} e-mail(s) de {e0['de']} indo para \"{envio_nf.PASTA_NF_ENVIADA}\" (pedido de {agente})")
        return {"ok": feitos > 0, "movidos": feitos, "motivo": "; ".join(sorted(f for f in falhas if f))}

    def _montar_correio(self):
        eventos = espelho_emails.dobrar_eventos(self.eventos_linhas + self.eventos_pendentes)
        entrada, enviados, _ = correio.juntar(self.emails, eventos, datetime.datetime.now(), self._alertas_documento(),
                                              self._alertas_nova_nota())
        convs = correio.conversas([e for e in entrada if e.get("pendente", True)])   # conversa = esperando resposta
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
        marcadas = self.ligacoes
        enviados = [{**e, "ligacao": ligacoes.chave_do_enviado(e) in marcadas} for e in enviados]
        return {"conversas": saida, "emails": emails, "enviados": enviados, "contagem": correio.contagem(convs, entrada),
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
        try:   # NF achadas pelo CPF/CNPJ (do pedido ou escrito no e-mail): vale também para e-mail sem formulário
            for i, itens in self._notas_por_documento().items():
                atuais = mapa.get(i, [])
                mapa[i] = atuais + [n for n in itens if n["rel"] not in {x.get("rel") for x in atuais}]
        except Exception:
            logger.exception("NF achadas por documento")
        self.notas_emails = mapa

    def _documentos_do_email(self, e, sol, buscar):
        """CPF/CNPJ do e-mail: os do pedido do formulário + os escritos no texto (guardados; o texto vem do Outlook do PC dono,
        então só se busca para e-mail candidato, no máximo `buscar` por vez)."""
        docs = set(nf_achadas._alvo(sol)["documentos"]) if sol else set()
        cache = self.__dict__.setdefault("_docs_do_email", {})
        if e["id"] not in cache and buscar[0] > 0:
            buscar[0] -= 1
            try:
                local = espelho_emails.item_local(e["id"]) if e["pc"] == socket.gethostname() else {}
                dados_texto = {"texto": local["texto"], "citado": local.get("citado", "")} if local.get("texto") else self.texto_email(e["id"])
            except Exception:
                return docs, False   # PC dono sem rede agora: tenta na próxima volta
            # o CPF/CNPJ muitas vezes só está na parte citada ("Mostrar mensagens anteriores") de uma resposta
            self.__dict__.setdefault("_textos_email", {})[e["id"]] = (dados_texto.get("texto", ""), dados_texto.get("citado", ""))
            cache[e["id"]] = (nf_achadas.documentos_do_texto(dados_texto.get("texto", "")) |
                              nf_achadas.documentos_do_texto(dados_texto.get("citado", "")) | nf_achadas.documentos_do_texto(e.get("previa", "")))
        return docs | cache.get(e["id"], set()), e["id"] in cache

    def _notas_por_documento(self):
        """{id do e-mail: [NF das pastas cujo CPF/CNPJ é o do e-mail]} — GATILHO (27/10/2026): nota nova na pasta aparece na etiqueta
        "NF pronta" do e-mail do hóspede, com ou sem formulário. Só lê; nunca envia nem move nada."""
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return {}
        agora = datetime.datetime.now()
        desde = (agora - datetime.timedelta(hours=nf_achadas.NOTA_PRONTA_HORAS)).timestamp()
        recentes = [(c, e) for c, e in indice.itens() if e.get("doc") and not e.get("sem_texto") and e.get("mtime", 0) >= desde]
        if not recentes:
            return {}
        palavras = set().union(*(nf_achadas.palavras_do_nome(e.get("nome", "")) for _c, e in recentes))
        corte = (agora - datetime.timedelta(days=15)).isoformat()
        buscar, saida, raiz = [8], {}, envio_nf.raiz_dropbox(self.cfg)
        entradas = [x for x in list(self.emails) if x["pasta"] == espelho_emails.ENTRADA]
        por_remetente = {}
        for x in entradas:
            por_remetente.setdefault((x.get("de") or "").lower(), []).append(x["id"])
        for e in sorted(entradas, key=lambda x: x["quando"], reverse=True):
            if e["quando"] < corte or {"formulario", "aviso"} & set(e.get("classes", [])):
                continue
            sol = self._solicitacao_do_email(e["de"])
            ja = [str(n) for n in ((self.estados.get(sol["chave"]) or {}).get("nfs", []) if sol else [])]
            cache = self.__dict__.get("_docs_do_email", {})
            candidato = bool(sol) or e["id"] in cache or bool(
                palavras & set(nf_achadas._palavras_texto(f"{e.get('nome', '')} {e.get('de', '')} {e.get('assunto', '')} {e.get('previa', '')}")))
            if not candidato:
                continue
            docs, _ = self._documentos_do_email(e, sol, buscar)
            for outro in por_remetente.get((e.get("de") or "").lower(), []):   # a resposta herda o documento do e-mail original
                docs = docs | self.__dict__.get("_docs_do_email", {}).get(outro, set())
            if docs:
                achadas = nf_achadas.notas_por_documento(indice, docs, agora, raiz, ja)
                if achadas:
                    saida[e["id"]] = achadas
        return saida

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
        """PC que não respondeu pela rede nos últimos 5 min fica de fora (usuário, 15/10/2026: o e-mail e o histórico
        demoravam porque cada pedido esperava 12 s pelo PC da Clara, que está em outra faixa de rede): usa a cópia."""
        agora, fora = time.monotonic(), getattr(self, "_sem_rede", {})
        return {p["pc"]: p["rede"] for p in self.pcs() if p.get("rede") and (p["online"] or not so_online)
                and p["pc"] != socket.gethostname() and agora - fora.get(p["pc"], -1e9) > SEM_REDE_SEGUNDOS}

    def _anotar_rede(self, respostas):
        fora = self.__dict__.setdefault("_sem_rede", {})
        for pc, r in (respostas or {}).items():
            if "não respondeu pela rede" in str((r or {}).get("erro", "")):
                fora[pc] = time.monotonic()
            elif r and "erro" not in r:
                fora.pop(pc, None)

    # --- chamadas que chegam dos outros PCs (rede_local) ---
    def rede_buscar(self, corpo):
        indice = getattr(self, "indice", None)
        if indice is not None and not corpo.get("vivo") and indice.total():
            r = indice.buscar(corpo.get("q", ""), limite=min(int(corpo.get("limite") or busca_outlook.LIMITE_POR_PC), 200))
            return {"resultados": [{**x, "pc": socket.gethostname()} for x in r], "completo": self.montador.pronto,
                    "fonte": "indice", "pc": socket.gethostname()}
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        rapido = bool(corpo.get("so_enviados"))   # só os Itens Enviados, com limite de tempo curto
        r = busca_outlook.buscar(ns, self._caixas_de_hotel(), corpo.get("q", ""), socket.gethostname(),
                                 limite=min(int(corpo.get("limite") or busca_outlook.LIMITE_POR_PC), 200),
                                 tempo_maximo=min(float(corpo.get("tempo") or busca_outlook.TEMPO_MAXIMO), busca_outlook.TEMPO_MAXIMO),
                                 pastas=((5, "enviado"),) if rapido else busca_outlook.PASTAS)
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

    def rede_anexo(self, corpo):
        """Anexo de um e-mail das caixas deste PC (foto, PDF do hóspede) pra ver no Painel. Só leitura."""
        entry = str(corpo.get("entry") or "") or espelho_emails.item_local(str(corpo.get("id", ""))).get("entry_id", "")
        if not entry:
            raise KeyError("e-mail não está mais no espelho deste PC")
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        return {**busca_outlook.ler_anexo(ns, entry, self._caixas_de_hotel(), str(corpo.get("nome", ""))), "pc": socket.gethostname()}

    def rede_enviar(self, corpo):
        """Pedido do robô (PC principal, 15/10/2026): manda o e-mail do formulário da própria caixa do hotel, que
        está neste Outlook, para ela mesma (envio_pc_dono.enviar_aqui)."""
        import pythoncom
        pythoncom.CoInitialize()
        app = outlook_vivo.aplicativo()
        return envio_pc_dono.enviar_aqui(app, app.GetNamespace("MAPI"), corpo, self._caixas_de_hotel())

    def rede_conferir_envio(self, corpo):
        import pythoncom
        pythoncom.CoInitialize()
        return envio_pc_dono.conferir_aqui(outlook_vivo.aplicativo().GetNamespace("MAPI"), corpo, self._caixas_de_hotel())

    def rede_enviar_receber(self, _corpo):
        """Outro PC (ou este Painel) pede o Enviar/Receber deste Outlook (27/10/2026): roda e espera acabar."""
        if not outlook_vivo.pode_usar():
            return {"erro": "Outlook fechado neste PC"}
        import pythoncom
        pythoncom.CoInitialize()
        r = enviar_receber.rodar_aqui(outlook_vivo.aplicativo().GetNamespace("MAPI"))
        self.versao_tela += 1
        return r

    def rede_caixas(self, _corpo):
        """Outro PC (ou este Painel) pergunta quais caixas daqui têm e-mail preso (27/10/2026)."""
        return {"pc": socket.gethostname(), "caixas": list(getattr(self, "caixas_presas", []) or [])}

    def rede_reiniciar_outlook(self, _corpo):
        """Fecha à força e abre de novo o Outlook DESTE PC (27/10/2026: o que o João fazia à mão quando parava de enviar)."""
        import pythoncom
        pythoncom.CoInitialize()
        r = outlook_vivo.reiniciar()
        self.versao_tela += 1
        return r

    def caixas_com_problema(self):
        """Pro botão de caixas: por PC com Outlook sem enviar/receber, o aviso e as caixas com e-mail preso (27/10/2026)."""
        demo = bool(getattr(self, "demo", False))
        pcs = {p["pc"]: p for p in self.pcs()}
        por_pc = {}
        for p in saude.problemas(list(pcs.values())):
            if p.get("tipo") == "caixa" and p.get("pc"):
                por_pc.setdefault(p["pc"], []).append(p["texto"])
        este = socket.gethostname()
        enderecos = {pc: pcs[pc].get("rede") for pc in por_pc if pc != este and pcs.get(pc, {}).get("rede")}
        det = {} if demo else rede_local.perguntar_a_todos(self.segredo, enderecos, "caixas", {}, tempo=6)
        if este in por_pc and not demo:
            det[este] = self.rede_caixas({})
        saida = []
        for pc, textos in por_pc.items():
            d = det.get(pc) or {}
            saida.append({"pc": pc, "agente": pcs[pc].get("agente") or pc, "textos": textos, "outlook": pcs[pc].get("outlook", ""),
                          "caixas": [c for c in d.get("caixas", []) if c.get("presos")], "erro": d.get("erro", "")})
        return {"pcs": saida, "este_pc": este}

    def reiniciar_outlook(self, pc, quem):
        if getattr(self, "so_ver", False):
            return {"erro": "Modo só leitura: não reinicia nada"}
        este = socket.gethostname()
        todos = {p["pc"]: p for p in self.pcs()}
        if getattr(self, "demo", False):
            time.sleep(4)
            return {"ok": True, "segundos": 4.0, "saiu": 3, "presos": 0}
        if pc and pc != este and pc not in todos:
            return {"erro": "PC desconhecido"}
        if not pc or pc == este:
            r = self.rede_reiniciar_outlook({})
        else:
            endereco = todos[pc].get("rede")
            if not todos[pc].get("online") or not endereco:
                return {"erro": f"{todos[pc].get('agente') or pc} está desligado ou sem rede: peça para reiniciar lá"}
            try:
                r = rede_local.perguntar(self.segredo, endereco, "reiniciar_outlook", {}, tempo=outlook_vivo.REINICIO_TEMPO_REDE)
            except Exception as e:
                r = {"erro": f"o PC não respondeu pela rede ({type(e).__name__})"}
        logger.warning(f"🔁 Reinício do Outlook de {pc or este} pedido por {quem}: {r}")
        return r

    def _er_terminou(self, _pc):
        self.__dict__.setdefault("acordar", threading.Event()).set()   # a tela relê já; o espelho vem da vigia do conferente
        self.versao_tela += 1

    def _enviar_receber(self):
        if getattr(self, "_er", None) is None:
            demo = bool(getattr(self, "demo", False))

            def local():
                if demo:
                    time.sleep(1.5)
                    return {"ok": True, "segundos": 1.5, "saiu": 0, "presos": 0}
                return self.rede_enviar_receber({})

            def remoto(pc, endereco):
                if demo:
                    time.sleep(2 + (hash(pc) % 40) / 10)
                    return {"ok": True, "segundos": 3.0, "saiu": 0, "presos": 0}
                return rede_local.perguntar(self.segredo, endereco, "enviar_receber", {}, tempo=enviar_receber.TEMPO_REDE)
            self._er = enviar_receber.EnviarReceber(
                socket.gethostname(), local, remoto,
                lambda: [{**p, "rede": p.get("rede") or ("demo" if demo else "")} for p in self.pcs()],
                PASTA_ESTADO / "enviar_receber_tempos.json", ao_terminar=self._er_terminou)
        return self._er

    def enviar_receber_todas(self, quem):
        if getattr(self, "so_ver", False):
            return {"erro": "Modo só leitura: não pede nada aos PCs"}
        return self._enviar_receber().iniciar(quem)

    def definir_robo_ligado(self, ligado, quem):
        """Liga ou pausa o robô (27/10/2026, só o João): é a caixa "Robô ligado?" da aba Status, a mesma que o robô lê antes de
        cada rodada. Desligado = nada é copiado nem enviado (os pedidos esperam) e o "Enviar agora" fica travado."""
        if getattr(self, "so_ver", False):
            return {"ok": False, "motivo": "Modo só leitura: não liga nem pausa o robô"}
        valor = "TRUE" if ligado else "FALSE"
        if not getattr(self, "demo", False):
            self.backend.escrever(self.cfg["planilha_central_id"], [(f"{nome_intervalo(self.cfg['aba_status'])}!B1", valor)])
        self.status[STATUS_ROTULO_A1] = valor
        logger.warning(f"🔌 Robô {'LIGADO' if ligado else 'PAUSADO (desligado)'} no Painel por {quem}")
        self.versao_tela += 1
        return {"ok": True, "ligado": bool(ligado)}

    def rede_ping(self, _corpo):
        return {"pc": socket.gethostname(), "agente": nome_do_agente(), "versao": self.versao}

    def marca_tela(self):
        """Muda quando a tela tem dado novo pra buscar (velocidade 3, 21/10/2026): leitura da Central, NF do Dropbox ou
        envio que terminou. A tela pergunta isto a cada 3 s e só relê quando muda."""
        envio = getattr(self, "envio_nf", None)
        locais = list(getattr(envio, "locais", {}).values())
        feitos = sum(1 for v in locais if (v or {}).get("estado") in ("enviado", "falhou"))
        return f"{getattr(self, 'versao_tela', 0)}.{len(locais)}.{feitos}"

    def rede_novidade(self, corpo):
        """O robô deste PC (ou o Painel de outro PC, repassando) gravou e-mail/NF novo na Central (21/10/2026): o laço
        relê já. Do robô daqui: repassa aos outros PCs uma vez (o repassado não é repassado de novo)."""
        acordar = self.__dict__.setdefault("acordar", threading.Event())
        if str((corpo or {}).get("o_que", "")) == "formulario":   # cópia rápida (23/10/2026): relê as abas dos hotéis já
            self.hoteis_lidos_em = -1e9
        acordar.set()
        if not (corpo or {}).get("repassado"):
            threading.Thread(target=self._repassar_novidade, args=(dict(corpo or {}),), daemon=True).start()
        return {"ok": True}

    def _repassar_novidade(self, corpo):
        enderecos = self._enderecos_rede()
        if not enderecos or not getattr(self, "segredo", None):
            return
        self._anotar_rede(rede_local.perguntar_a_todos(self.segredo, enderecos, "novidade",
                                                       {"o_que": str(corpo.get("o_que", ""))[:20], "repassado": True},
                                                       tempo=5))

    def olhar_dropbox(self):
        """Pasta de notas do Dropbox mudou (NF nova)? Refaz a lista e as NFs dos e-mails na hora (21/10/2026; antes a
        lista valia 5 min e as NFs dos e-mails 2 min). -> True quando mudou."""
        if time.monotonic() - self.dropbox_olhado < DROPBOX_OLHAR_SEGUNDOS:
            return False
        self.dropbox_olhado = time.monotonic()
        marca = envio_nf.marca_das_pastas(self.cfg)
        antes, self.marca_dropbox = self.marca_dropbox, marca
        if antes is None or marca == antes:
            return False
        envio_nf.listar_notas_dropbox(self.cfg, forcar=True)
        self.atualizar_notas_emails(forcar=True)
        self.versao_tela += 1
        logger.info("🧾 NF nova no Dropbox — NFs dos e-mails refeitas")
        return True

    def rede_envio_nf(self, corpo):
        """Envio direto (21/10/2026): outro PC gravou um pedido para a caixa que está aqui e avisa na hora."""
        return self.envio_nf.receber_pela_rede(corpo)

    def _avisar_dono_envio(self, pc, corpo):
        """Avisa o PC dono pela rede. Sem caminho até ele (outra faixa de rede, firewall, desligado) = erro, e o pedido
        segue pela fila Envios_NF como sempre."""
        endereco = self._enderecos_rede().get(pc)
        if not endereco or not getattr(self, "segredo", None):
            raise RuntimeError("sem caminho direto até ele")
        r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "envio_nf", corpo,
                                         tempo=envio_nf.TEMPO_AVISO_DONO).get(pc, {})
        self._anotar_rede({pc: r})
        if "erro" in r:
            raise RuntimeError(r["erro"])
        return r

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
            r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "texto", {"id": id_email, "entry": entry}, tempo=6).get(pc, {})
            self._anotar_rede({pc: r})
            if "erro" not in r:
                return {**r, "origem": "ao vivo"}
        if not id_email:
            raise KeyError(f"o PC {pc} não respondeu pela rede agora — tente de novo em instantes")
        return {**self._texto_da_planilha(pc, id_email), "origem": "cópia (PC dono sem rede)"}

    def anexo_email(self, id_email="", pc="", entry="", nome=""):
        """Anexo pedido ao vivo pro PC dono (nada fica guardado). PC dono desligado: não tem como (só ele tem o Outlook)."""
        if not nome:
            raise ValueError("nome do anexo")
        if id_email and not pc:
            pc = self._email(id_email)["pc"]
        if pc == socket.gethostname() or not pc:
            return self.rede_anexo({"id": id_email, "entry": entry, "nome": nome})
        endereco = self._enderecos_rede().get(pc)
        if not (endereco and self.segredo):
            raise KeyError("o PC dono desse e-mail está desligado ou sem rede agora: o anexo só pode ser aberto por lá")
        r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "anexo", {"id": id_email, "entry": entry, "nome": nome},
                                         tempo=45).get(pc, {})
        self._anotar_rede({pc: r})
        if "erro" in r:
            raise KeyError(f"o PC dono não mandou o anexo: {r['erro']}")
        return r

    def _texto_da_planilha(self, pc, id_email):
        e = self._email(id_email)
        versao, textos = self.textos_cache.get(pc, ("", {}))
        if versao != e.get("versao_texto") or id_email not in textos:
            aba = espelho_emails.nome_aba_textos(pc)
            textos = espelho_emails.ler_textos(self.backend.ler_abas(self.central, [aba])[0].get(aba, []))
            self.textos_cache[pc] = (e.get("versao_texto"), textos)
        texto, citado = textos.get(id_email, ("", ""))
        return {"texto": texto or e.get("previa", ""), "citado": citado, "pc": pc}

    def buscar_outlook(self, termo, vivo=False):
        """Pergunta aos PCs ligados (este incluído) ao mesmo tempo. Cada um responde pelo índice local (milissegundos);
        vivo=True (botão "Procurar também no Outlook"): direto no Outlook de cada um, como antes de 20/10/2026."""
        termo = busca_outlook.limpar_termo(termo)
        if len(termo) < 3:
            return {"resultados": [], "pcs": {}, "termo": termo}
        respostas = {}
        enderecos = self._enderecos_rede()
        import threading as _t
        local = {}
        fio = _t.Thread(target=lambda: local.update(r=self._buscar_local(termo, vivo)))
        fio.start()
        if enderecos and self.segredo:
            respostas = rede_local.perguntar_a_todos(self.segredo, enderecos, "buscar", {"q": termo, "vivo": vivo},
                                                     tempo=8 if vivo else 4)
            self._anotar_rede(respostas)
        fio.join(busca_outlook.TEMPO_MAXIMO + 3)
        respostas[socket.gethostname()] = local.get("r", {"erro": "o Outlook deste PC não respondeu a tempo"})
        pcs = self._pcs_por_nome()
        for p in pcs.values():
            if p["pc"] not in respostas:
                respostas[p["pc"]] = {"erro": "desligado" if not p["online"] else "sem rede agora (usa a cópia)" if p.get("rede")
                                      else "sem endereço de rede (atualize o Painel dele)"}
        resultados = [r for resp in respostas.values() for r in resp.get("resultados", [])]
        resultados.sort(key=lambda r: r["quando"], reverse=True)
        situacao = {pc: ({"ok": True, "achados": len(r.get("resultados", [])), "completo": r.get("completo", True),
                          "fonte": r.get("fonte", "outlook")}
                         if "erro" not in r else {"ok": False, "erro": r["erro"]}) for pc, r in respostas.items()}
        if self._falta_envio_do_hospede(termo, vivo, resultados, situacao):
            achados = self._enviados_rapido(termo, enderecos)
            ids = {r["id"] for r in resultados}
            resultados += [r for r in achados if r["id"] not in ids]
            resultados.sort(key=lambda r: r["quando"], reverse=True)
        return {"resultados": resultados, "pcs": situacao, "termo": termo, "vivo": bool(vivo),
                "agentes": {p["pc"]: p["agente"] for p in pcs.values()}}

    @staticmethod
    def _falta_envio_do_hospede(termo, vivo, resultados, situacao):
        """Pesquisa por endereço de hóspede (22/10/2026) e nenhum e-mail ENVIADO apareceu, com algum PC respondendo pelo
        índice ainda incompleto (ou direto do Outlook sem pasta de enviados): vale a consulta rápida nos Itens Enviados."""
        if vivo or "@" not in termo or any(r.get("pasta") == "enviado" for r in resultados):
            return False
        return any(s.get("ok") and not (s.get("fonte") == "indice" and s.get("completo", True)) for s in situacao.values())

    def _enviados_rapido(self, termo, enderecos):
        """Consulta só nos Itens Enviados do Outlook de cada PC, com limite de ~1 s. Guarda 60 s (o mesmo endereço
        digitado de novo não repete). Qualquer falha = sem extra: o resultado normal já está na tela."""
        cache = self.__dict__.setdefault("_enviados_rapido_cache", {})
        agora = time.monotonic()
        if termo in cache and agora - cache[termo][0] < 60:
            return cache[termo][1]
        corpo = {"q": termo, "vivo": True, "so_enviados": True, "tempo": ENVIADOS_RAPIDO_SEGUNDOS, "limite": 20}
        achados, local = [], {}
        fio = threading.Thread(target=lambda: local.update(r=self._buscar_local_rapido(corpo)))
        fio.start()
        try:
            if enderecos and getattr(self, "segredo", None):
                resp = rede_local.perguntar_a_todos(self.segredo, enderecos, "buscar", corpo, tempo=ENVIADOS_RAPIDO_SEGUNDOS + 1.5)
                achados += [x for r in resp.values() for x in r.get("resultados", [])]
        except Exception:
            logger.debug("enviados rápido pela rede", exc_info=True)
        fio.join(ENVIADOS_RAPIDO_SEGUNDOS + 2)
        achados += (local.get("r") or {}).get("resultados", [])
        achados = [x for x in achados if x.get("pasta") == "enviado"]
        cache[termo] = (agora, achados)
        return achados

    def _buscar_local_rapido(self, corpo):
        try:
            return self.rede_buscar(corpo)
        except Exception:
            logger.debug("enviados rápido neste PC", exc_info=True)
            return {}

    def _buscar_local(self, termo, vivo=False):
        try:
            return self.rede_buscar({"q": termo, "vivo": vivo})
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

    def marcar_urgencia(self, id_email, marcar, agente):
        """Botão direito (usuário, 20/10/2026): vale na hora pra equipe (Eventos_Correio) e o PC dono põe a categoria no
        Outlook, que é onde fica guardado (o evento some na faxina de 3 dias; a categoria não)."""
        if marcar not in ("urgente", "normal"):
            raise ValueError("marcar: urgente ou normal")
        e = self._email(id_email)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, mensagem=marcar, responder=e["id"],
                                acao=envio_nf.URGENCIA)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "URGENTE" if marcar == "urgente" else "NAO_URGENTE", agente)
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
        selo = str(corpo.get("selo") or "")   # assinatura padrão também no encaminhar (13/10/2026)
        return self.envio_nf.pedir(sol, para, assunto, e["caixa"], [], quem, str(corpo.get("corpo", "")),
                                   selo=selo if envio_nf.caminho_selo(selo) else "", responder=e["id"], acao=envio_nf.ENCAMINHAR)

    def opcoes_email(self, id_email):
        e = self._email(id_email)
        destino, motivo = self.envio_nf.destino_para(e["caixa"], aceitar_desligado=True)
        sol = self._solicitacao_do_email(e["de"])
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg) if sol else []
        if not sugestoes:   # e-mail sem formulário (ex.: recepção repassando o pedido): a NF achada pelo nº/nome
            sugestoes = envio_nf.notas_do_email(e, self.cfg)
        vistas = {x.get("rel") for x in sugestoes}   # + as achadas pelo CPF/CNPJ (gatilho da nota nova)
        sugestoes = sugestoes + [n for n in self.notas_emails.get(e["id"], []) if n.get("rel") not in vistas]
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
                "corpo_nf": envio_nf.mensagem_padrao(self.cfg), "assinatura": "", "assinatura_com_mensagem": False, "selos": envio_nf.selos(),
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
        r = self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, str(corpo.get("corpo", "")), cc,
                                selo if envio_nf.caminho_selo(selo) else "", livre=True, **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, sol["hotel"], conta, para, assunto)

    def responder_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        # formulário do Emissor Automático (20/10/2026): o pedido é o do hóspede do Para, não o do remetente (o Emissor)
        do_form = self._solicitacao_do_email(para.lower()) if "formulario" in (e.get("classes") or []) and "@" in para else None
        sol = do_form or self._solicitacao_do_email(e["de"]) or {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"],
                                                                 "nome": e["nome"] or e["de"]}
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
        r = self.envio_nf.pedir(sol, para, assunto, e["caixa"], anexos, quem, str(corpo.get("corpo", "")), cc,
                                selo if envio_nf.caminho_selo(selo) else "", responder=e["id"], **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, e["hotel"] or sol["hotel"], e["caixa"], para, assunto)

    def iniciar_nf_achadas(self):
        """Liga o fio que lê as notas novas das pastas do Dropbox e guarda o CPF/CNPJ do tomador (27/10/2026)."""
        if not (self.cfg.get("dropbox_notas") or {}).get("ativo"):
            return

        def ler(caminho):
            from conferente import texto_de_arquivo_dropbox
            return texto_de_arquivo_dropbox(caminho)
        self.nf_indice = nf_achadas.Indice(PASTA_ESTADO / "nf_achadas.json")
        nf_achadas.iniciar(self.cfg, self.nf_indice, ler, ao_novas=lambda: self.atualizar_notas_emails(forcar=True))

    def _nf_achadas(self, sol):
        """-> (sugestões de NF pelo documento, avisos). A tag ✅ não é prova: confere se o envio existe nos Itens Enviados."""
        est = self.estados.get(sol["chave"]) or dados.estado_inicial()
        nfs = [str(n) for n in est.get("nfs", [])]
        avisos = []
        enviados = list(self.enviados_correio)
        if nfs and enviados:
            sem = nf_achadas.sem_envio_confirmado(nfs, enviados, envio_nf.destinatarios(sol))
            if sem:
                avisos.append(f"Marcado como enviado, mas não achei o envio da NF {', '.join(sem)} nos Itens Enviados. "
                              "A resposta do hóspede com a nota anexada não conta como envio.")
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return [], avisos
        limite = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
        ligadas, outros = set(), {}
        for o in self.solicitacoes:
            if o["chave"] == sol["chave"] or (o.get("data") or "") < limite:
                continue
            for n in (self.estados.get(o["chave"]) or {}).get("nfs", []):
                ligadas.add((o.get("hotel", ""), str(n)))
            alvo = nf_achadas._alvo(o)
            for d in alvo["documentos"]:
                outros.setdefault(d, []).append(alvo)
        return nf_achadas.achadas_do_pedido(indice, sol, nfs, ligadas, outros, raiz=envio_nf.raiz_dropbox(self.cfg)), avisos

    def opcoes_envio(self, chave_sol):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        conta = self.cadastro.dados(sol["hotel"]).get("email", "")
        destino, motivo = self.envio_nf.destino_para(conta, aceitar_desligado=True)
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg)
        try:   # NF achadas pelo CPF/CNPJ dentro do PDF (27/10/2026); nunca anexa nem envia sozinha
            achadas, avisos_nf = self._nf_achadas(sol)
        except Exception:
            logger.exception("NF achadas")
            achadas, avisos_nf = [], []
        vistas = {x.get("rel") for x in sugestoes}
        sugestoes = sugestoes + [a for a in achadas if a["rel"] not in vistas]
        try:
            assinatura = envio_nf.assinatura_previa(conta, nome_do_agente())
        except Exception:
            logger.exception("prévia da assinatura")
            assinatura = ""
        com_mensagem = envio_nf.assinatura_tem_mensagem(assinatura)
        selos = envio_nf.selos()
        return {"para": envio_nf.destinatarios(sol), "conta_de": conta, "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes, "avisos_nf": avisos_nf,
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
        r = self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, corpo.get("corpo"), cc,
                                selo if envio_nf.caminho_selo(selo) else "", **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, sol["hotel"], conta, para, assunto)

    # ---------- pedido por ligação (usuário, 22/10/2026) ----------
    def _gravar_ligacao(self, chave, acao, agente, hotel="", caixa="", para="", assunto=""):
        linha = ligacoes.evento(chave, acao, agente, hotel, caixa, para, assunto)
        self.backend.anexar_linhas(self.central, ligacoes.ABA, [linha])
        with self.lock:
            self.ligacoes_linhas = (self.ligacoes_linhas or [ligacoes.CABECALHO]) + [linha]
            self.ligacoes = ligacoes.dobrar(self.ligacoes_linhas)
            self.versao_tela = getattr(self, "versao_tela", 0) + 1

    def _marcar_ligacao_do_envio(self, r, corpo, quem, hotel, caixa, para, assunto):
        """Botão "Ligação" ligado na tela de escrever: marca o envio (chave = id ENV-…). O e-mail já está na fila; se a
        marca não gravar, o envio segue e a tela avisa pra marcar depois em Itens Enviados."""
        if not (r.get("ok") and corpo.get("ligacao") and r.get("id")):
            return r
        try:
            self._gravar_ligacao(r["id"], ligacoes.MARCAR, quem, hotel, caixa, para, assunto)
            logger.info(f"📞 {r['id']}: marcado como ligação ({hotel}, por {quem})")
        except Exception as e:
            logger.warning(f"⚠️ {r['id']}: não consegui gravar a marca de ligação ({e})")
            return {**r, "aviso_ligacao": "O e-mail vai sair, mas a marca de ligação não gravou. Marque depois em Itens Enviados (botão direito)."}
        return r

    def marcar_ligacao(self, id_email, marcar, agente):
        """Botão direito num e-mail de Itens Enviados: "Marcar como ligação" / "Tirar marca de ligação"."""
        with self.lock:
            e = next((x for x in self.enviados_correio if x.get("id") == id_email), None)
        if e is None:
            raise KeyError("e-mail enviado não encontrado (pode ter passado das 72 h)")
        chave = ligacoes.chave_do_enviado(e)
        if bool(marcar) == (chave in self.ligacoes):
            return {"ok": True, "ligacao": bool(marcar)}
        self._gravar_ligacao(chave, ligacoes.MARCAR if marcar else ligacoes.DESMARCAR, agente, e.get("hotel", ""),
                             e.get("caixa", ""), e.get("para", ""), e.get("assunto", ""))
        logger.info(f"📞 {chave}: {'marcado' if marcar else 'desmarcado'} como ligação em Itens Enviados, por {agente}")
        return {"ok": True, "ligacao": bool(marcar)}

    def _ligacoes_de_envios_falhos(self):
        """Envio marcado que falhou: o PC que marcou tira a marca (o reenvio é que conta)."""
        if getattr(self, "so_ver", False) or not self.ligacoes:
            return
        for chave in ligacoes.envios_falhos_a_desmarcar(self.ligacoes, self.envio_nf.fila, socket.gethostname()):
            m = self.ligacoes[chave]
            self._gravar_ligacao(chave, ligacoes.DESMARCAR, m["agente"], m["hotel"], m["caixa"], m["para"], m["assunto"])
            logger.info(f"📞 {chave}: o envio falhou — marca de ligação retirada (o reenvio é que conta)")

    def resumo_ligacoes(self):
        """Cartão Ligações da Visão geral; "de N envios" = envios do Painel que saíram hoje (a fila guarda 3 dias)."""
        hoje = datetime.date.today().isoformat()
        envios = sum(1 for e in list(getattr(self.envio_nf, "fila", {}).values())
                     if e.get("resultado") == envio_nf.ENVIADO and str(e.get("pedido_em", ""))[:10] == hoje
                     and not (e.get("pedido") or {}).get("acao"))
        return ligacoes.resumo(self.ligacoes, envios)

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
            if url.path == "/api/versao":
                return self._json({"v": estado.marca_tela()})
            if url.path == "/api/estado":
                dias = int(parse_qs(url.query).get("dias", ["45"])[0] or 0)
                estado.vista_atual = parse_qs(url.query).get("vista", [""])[0]
                return self._json({
                    "agente": nome_do_agente(), "pc": pc, "erro": estado.erro, "operadores": operadores_deste_pc(cfg, liberado()),
                    "atualizado_em": estado.atualizado_em.isoformat(timespec="seconds") if estado.atualizado_em else "",
                    "atualizar_segundos": int(cfg.get("app", {}).get("atualizar_segundos", 15)),
                    "status": estado.resumo_status(), "fila": estado.fila_da_tela(dias), "pcs": estado.pcs(),
                    "caixa_pcs": estado.resumo_caixa(), "saude": estado.problemas_de_saude(),
                    "hoteis": estado.hoteis_por_agente(), "ligacoes": estado.resumo_ligacoes(),
                    "demo": bool(getattr(estado, "demo", False)), "pagina": _marca_pagina(), "so_ver": bool(getattr(estado, "so_ver", False)),
                    "admin": e_admin_aqui(estado.cfg, nome_do_agente(), liberado()),
                    "tema": ler_prefs().get("tema", ""),
                }, comparar=True)
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
                if url.path == "/api/nf_cobre":
                    return self._json(estado.nf_cobre(q.get("id", "")))
                if url.path == "/api/caixas":
                    return self._json(estado.caixas_com_problema())
                if url.path == "/api/enviar_receber/status":
                    return self._json(estado._enviar_receber().status(q.get("id", "")))
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
                    return self._json({"emails": estado.lista_emails(), "este_pc": pc}, comparar=True)
                if url.path == "/api/correio":
                    return self._json(estado.lista_correio(), comparar=True)
                if url.path == "/api/correio/conversa":
                    return self._json(estado.conversa(q.get("de", "")))
                if url.path == "/api/correio/texto":
                    return self._json(estado.texto_email(q.get("id", ""), q.get("pc", ""), q.get("entry", "")))
                if url.path == "/api/correio/anexo":
                    return self._json(estado.anexo_email(q.get("id", ""), q.get("pc", ""), q.get("entry", ""), q.get("nome", "")))
                if url.path == "/api/correio/buscar":
                    return self._json(estado.buscar_outlook(q.get("q", ""), q.get("vivo", "") == "1"))
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
            if getattr(estado, "so_ver", False) and path not in ("/api/agente", "/api/atualizar"):
                return self._json({"ok": False, "motivo": "Modo casa: só visualização. Faça isso no PC do trabalho."})
            try:
                if path == "/api/acao":
                    r = estado.registrar(nome_do_agente(), pc, corpo["chave"], corpo["acao"], corpo.get("valor", ""))
                    return self._json(r)
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
                    if nome not in operadores_deste_pc(carregar_config(), liberado()):
                        return self._json({"ok": False, "motivo": f"O usuário {nome} só pode ser usado no PC dele."}, 403)
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
                if path == "/api/correio/urgencia":
                    return self._json(estado.marcar_urgencia(str(corpo.get("id", "")), str(corpo.get("marcar", "")), nome_do_agente()))
                if path == "/api/correio/mover_nf":
                    return self._json(estado.mover_email_nf(str(corpo.get("id", "")), nome_do_agente()))
                if path == "/api/correio/concluir":
                    return self._json(estado.concluir_conversa(str(corpo.get("id", "")), nome_do_agente()))
                if path == "/api/robo/ligado":
                    if not e_admin_aqui(estado.cfg, nome_do_agente(), liberado()):
                        return self._json({"ok": False, "motivo": "Só o João liga ou pausa o robô, no PC dele."}, 403)
                    return self._json(estado.definir_robo_ligado(bool(corpo.get("ligado")), nome_do_agente()))
                if path == "/api/outlook/reiniciar":
                    return self._json(estado.reiniciar_outlook(str(corpo.get("pc", "")), nome_do_agente()))
                if path == "/api/enviar_receber":
                    return self._json(estado.enviar_receber_todas(nome_do_agente()))
                if path == "/api/ligacao":
                    return self._json(estado.marcar_ligacao(str(corpo.get("id", "")), bool(corpo.get("marcar")), nome_do_agente()))
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


def _kw_ligacao(corpo):
    """Botão Ligação ligado na tela de escrever: o pedido de envio leva ligacao=True (categoria LIGAÇÃO no Outlook).
    Desligado: nenhum argumento a mais."""
    return {"ligacao": True} if (corpo or {}).get("ligacao") else {}


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
    import cota_google
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
