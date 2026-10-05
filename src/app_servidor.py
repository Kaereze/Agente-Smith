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
import envio_nf
import fiscal_intelligence
import painel_metricas as metricas
from arquivos import salvar_json
from hoteis import CadastroHoteis
from app_envio import Envio
from config import PASTA_ESTADO, PASTA_PROJETO, caminho_chave_google, carregar_config, e_principal
from log_util import configurar_logging
from sheets import (LINHA_COMANDO, LINHA_PEDIDO, STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba)
from tratamento import normalizar

logger = configurar_logging("app")

PORTA = 8765
PASTA_UI = PASTA_PROJETO / "app_ui"
CAMINHO_PREFS = PASTA_ESTADO / "app.json"
JANELA_ABERTA_SEGUNDOS = 90     # a janela pede dados a cada 15 s; sem pedido há 90 s = fechada
CAMINHO_CACHE = PASTA_ESTADO / "painel_cache.pkl"
SALVAR_CACHE_SEGUNDOS = 120
VERSAO_CACHE = 1
ESTATICOS = {   # lista fechada: nada fora daqui é servido do disco
    "/icone.png": ("icone.png", "image/png"),
    "/favicon.ico": ("icone.ico", "image/x-icon"),
    "/graficos.js": ("graficos.js", "text/javascript; charset=utf-8"),
    "/painel.js": ("painel.js", "text/javascript; charset=utf-8"),
}
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


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
        self.desde = datetime.date.fromisoformat(painel.get("desde", "2026-09-01"))
        self.fi_id, self.fi_minutos = painel.get("fiscal_intelligence_id", ""), int(painel.get("fi_minutos", 5))
        self.ignorar = list(painel.get("ignorar_hoteis", []))
        self.fi, self.fi_lido, self.fi_erro = None, -1e9, ""
        self.cache_salvo = -1e9

    def _abas(self):
        if self.relogio() - self.abas_lidas_em > 600:
            marcador = normalizar(self.cfg.get("marcador_aba_respostas", "(respostas)"))
            ignoradas = {normalizar(a) for a in self.cfg.get("abas_ignoradas", [])}
            todas = self.backend.listar_abas(self.central)
            aba_cad = self.cfg["aba_cadastro_hoteis"]
            cad, _ = self.backend.ler_abas(self.central, [aba_cad])
            self.cadastro = CadastroHoteis(cad.get(aba_cad, []), self.cfg.get("apelidos_hoteis", {}),
                                           self.cfg.get("cadastro_colunas"))
            self.abas_hotel = {a: self.cadastro.canonico(nome_do_hotel_pela_aba(a)) or nome_do_hotel_pela_aba(a)
                               for a in todas if marcador in normalizar(a) and normalizar(a) not in ignoradas}
            for aba, cab in ((dados.ABA_TRATAMENTO, dados.CABECALHO_TRATAMENTO), (envio_nf.ABA_FILA, envio_nf.CAB_FILA),
                             (envio_nf.ABA_ANEXOS, envio_nf.CAB_ANEXOS), (envio_nf.ABA_PCS, envio_nf.CAB_PCS)):
                if aba not in todas:
                    self.backend.criar_aba_log(self.central, aba, cab)
            self.abas_lidas_em = self.relogio()
        return self.abas_hotel

    def atualizar(self):
        try:
            abas = self._abas()
            status_aba = self.cfg["aba_status"]
            lidas, erros = self.backend.ler_abas(self.central, list(abas) + [dados.ABA_TRATAMENTO, status_aba,
                                                                              envio_nf.ABA_FILA, envio_nf.ABA_PCS])
            solicitacoes = []
            for aba, hotel in abas.items():
                solicitacoes += dados.ler_solicitacoes(aba, hotel, lidas.get(aba, []), self.cfg)
            status = {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in lidas.get(status_aba, []) if l}
            with self.lock:
                self.solicitacoes = solicitacoes
                self.estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))
                self.status = status
                self.atualizado_em, self.erro = dados.agora(), ""
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler a planilha ({e})")
            self.erro = str(e)[:200]
            return
        try:
            self.envio_nf.tick(lidas, nome_do_agente())
        except Exception:
            logger.exception("fila de envio de NF")

    def registrar_nf_enviada(self, pedido, quem):
        """NF enviada pelo Painel: entra no pedido como emitida (todos os PCs veem)."""
        pc, quando = socket.gethostname(), dados.agora()
        linhas = [dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.NF, nf)
                  for nf in pedido.get("nfs", [])]
        linhas.append(dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.OBS,
                                   f"\"{pedido['assunto']}\" enviada ao hóspede ({pedido['para']}) pela caixa {pedido['conta_de']}"))
        self.backend.anexar_linhas(self.central, dados.ABA_TRATAMENTO, linhas)
        self.reler_tratamento()

    def opcoes_envio(self, chave_sol):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        conta = self.cadastro.dados(sol["hotel"]).get("email", "")
        destino, motivo = self.envio_nf.destino_para(conta)
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg)
        try:
            assinatura = envio_nf.assinatura_previa(conta, nome_do_agente())
        except Exception:
            logger.exception("prévia da assinatura")
            assinatura = ""
        com_mensagem = envio_nf.assinatura_tem_mensagem(assinatura)
        return {"para": envio_nf.destinatarios(sol), "conta_de": conta, "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": sol["nome"], "hotel": sol["hotel"],
                "corpo": "" if com_mensagem else envio_nf.mensagem_padrao(self.cfg),
                "assinatura": assinatura, "assinatura_com_mensagem": com_mensagem}

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
        return self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, corpo.get("corpo"), cc)

    def situacao_envio(self, id_envio):
        local = self.envio_nf.locais.get(id_envio)
        if local and local["estado"] != "enviando":
            return local
        fresca = envio_nf.dobrar_fila(self.backend.ler_abas(self.central, [envio_nf.ABA_FILA])[0].get(envio_nf.ABA_FILA, [[]]))
        return self.envio_nf.situacao(id_envio, fresca)

    def reler_tratamento(self):
        lidas, _ = self.backend.ler_abas(self.central, [dados.ABA_TRATAMENTO])
        with self.lock:
            self.estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))

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
            return dados.montar_fila(self.solicitacoes, self.estados, dados.nfs_do_controle(controle), desde)

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

    def _periodo(self, ini, fim):
        hoje = datetime.date.today()
        ini = max(datetime.date.fromisoformat(ini) if ini else hoje.replace(day=1), self.desde)
        fim = min(datetime.date.fromisoformat(fim) if fim else hoje, hoje)
        return ini, max(fim, ini)

    def _ignorados(self):
        return {self.cadastro.canonico(h) or h for h in self.ignorar}

    def _fila_do_painel(self):
        ign = self._ignorados()
        return [s for s in self.fila(desde=self.desde.isoformat()) if s["hotel"] not in ign]

    def painel(self, ini, fim):
        ini, fim = self._periodo(ini, fim)
        hoje = datetime.date.today()
        fila = self._fila_do_painel()
        fi = self.fi or {"metricas": [], "fins_de_semana": {}, "saude": {}, "avisos": []}
        return {"ini": ini.isoformat(), "fim": fim.isoformat(), "desde": self.desde.isoformat(),
                "visao": metricas.visao_geral(fi["metricas"], fila, ini, fim, hoje, fi["fins_de_semana"]),
                "hoteis": metricas.tabela_hoteis(fi["metricas"], fila, ini, fim, hoje, self.cadastro, self._ignorados()),
                "saude": fi["saude"], "avisos": fi["avisos"], "fi_erro": self.fi_erro,
                "fi_lido_em": fi["lido_em"].isoformat(timespec="seconds") if fi.get("lido_em") else ""}

    def hotel(self, nome, ini, fim):
        ini, fim = self._periodo(ini, fim)
        fi = self.fi or {"metricas": [], "fins_de_semana": {}}
        return metricas.ficha_hotel(nome, fi["metricas"], self._fila_do_painel(), ini, fim,
                                    datetime.date.today(), fi["fins_de_semana"], self.cadastro)

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
                html = (PASTA_UI / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                corpo = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            estatico = ESTATICOS.get(url.path)
            if estatico:
                arquivo, tipo = estatico
                corpo = (PASTA_UI / arquivo).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            if url.path == "/api/estado":
                dias = int(parse_qs(url.query).get("dias", ["45"])[0] or 0)
                return self._json({
                    "agente": nome_do_agente(), "pc": pc, "erro": estado.erro, "operadores": operadores,
                    "atualizado_em": estado.atualizado_em.isoformat(timespec="seconds") if estado.atualizado_em else "",
                    "atualizar_segundos": int(cfg.get("app", {}).get("atualizar_segundos", 15)),
                    "status": estado.resumo_status(), "fila": estado.fila(dias),
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
            except KeyError as e:
                return self._json({"erro": str(e).strip("'\"")}, 404)
            except ValueError as e:
                return self._json({"erro": f"parâmetro inválido: {e}"}, 400)
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
            try:
                if path == "/api/acao":
                    r = estado.registrar(nome_do_agente(), pc, corpo["chave"], corpo["acao"], corpo.get("valor", ""))
                    return self._json(r)
                if path == "/api/agente":
                    nome = str(corpo.get("nome", "")).strip()[:40]
                    if nome not in operadores:
                        return self._json({"ok": False, "motivo": "operador desconhecido"}, 400)
                    salvar_json(CAMINHO_PREFS, {"agente": nome})
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
    cfg = carregar_config()
    estado = Estado(BackendGoogle(caminho_chave_google(cfg)), cfg)
    if estado.carregar_cache():
        logger.info(f"📦 Último estado carregado do disco ({estado.atualizado_em:%d/%m %H:%M}) — atualizando em seguida.")
    token = secrets.token_urlsafe(24)
    ultimo_uso = [-1e9]
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), criar_handler(estado, cfg, token, ultimo_uso))
    app = cfg.get("app", {})
    em_uso, em_fundo = int(app.get("atualizar_segundos", 15)), int(app.get("atualizar_segundos_fundo", 60))

    def laco():
        """Fica rodando enquanto o PC estiver ligado. Janela aberta: relê rápido; fechada: devagar (cota da API)."""
        while True:
            estado.atualizar()
            estado.atualizar_fi()
            estado.salvar_cache()
            inicio = time.monotonic()
            while True:
                aberta = time.monotonic() - ultimo_uso[0] < JANELA_ABERTA_SEGUNDOS
                if time.monotonic() - inicio >= (em_uso if aberta else em_fundo):
                    break
                time.sleep(1)

    threading.Thread(target=laco, daemon=True).start()
    logger.info(f"🖥️ Painel Notas Fiscais no ar em http://127.0.0.1:{PORTA}/ · agente {nome_do_agente()}")
    if not sem_janela:
        abrir_janela()
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
