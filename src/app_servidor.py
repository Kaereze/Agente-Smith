"""Painel Notas Fiscais: servidor HTTP só em 127.0.0.1 + janela do Edge em modo aplicativo.

    python src\\app_servidor.py            abre a janela (ou reaproveita a que já está rodando)
    python src\\app_servidor.py --sem-janela

Todos os PCs leem e gravam a mesma Planilha Central; o que muda num aparece nos outros
na próxima atualização (app.atualizar_segundos no config).
"""
import datetime
import json
import os
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
from arquivos import salvar_json
from config import PASTA_ESTADO, PASTA_PROJETO, caminho_chave_google, carregar_config
from log_util import configurar_logging
from sheets import (LINHA_COMANDO, LINHA_PEDIDO, STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba)
from tratamento import normalizar

logger = configurar_logging("app")

PORTA = 8765
PASTA_UI = PASTA_PROJETO / "app_ui"
CAMINHO_PREFS = PASTA_ESTADO / "app.json"
FECHAR_SEM_USO_SEGUNDOS = 3 * 60
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

    def __init__(self, backend, cfg, relogio=time.monotonic):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.central = cfg["planilha_central_id"]
        self.lock = threading.Lock()
        self.abas_hotel, self.abas_lidas_em = {}, -1e9
        self.solicitacoes, self.estados, self.status = [], {}, {}
        self.atualizado_em, self.erro = None, ""

    def _abas(self):
        if self.relogio() - self.abas_lidas_em > 600:
            marcador = normalizar(self.cfg.get("marcador_aba_respostas", "(respostas)"))
            ignoradas = {normalizar(a) for a in self.cfg.get("abas_ignoradas", [])}
            todas = self.backend.listar_abas(self.central)
            self.abas_hotel = {a: nome_do_hotel_pela_aba(a) for a in todas
                               if marcador in normalizar(a) and normalizar(a) not in ignoradas}
            if dados.ABA_TRATAMENTO not in todas:
                self.backend.criar_aba_log(self.central, dados.ABA_TRATAMENTO, dados.CABECALHO_TRATAMENTO)
            self.abas_lidas_em = self.relogio()
        return self.abas_hotel

    def atualizar(self):
        try:
            abas = self._abas()
            status_aba = self.cfg["aba_status"]
            lidas, erros = self.backend.ler_abas(self.central, list(abas) + [dados.ABA_TRATAMENTO, status_aba])
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

    def fila(self, dias):
        desde = (datetime.date.today() - datetime.timedelta(days=dias)).isoformat() if dias else None
        try:
            controle = json.load(open(PASTA_ESTADO / "controle_nf.json", encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            controle = {}
        with self.lock:
            return dados.montar_fila(self.solicitacoes, self.estados, dados.nfs_do_controle(controle), desde)

    def resumo_status(self):
        s = self.status
        return {"ligado": normalizar(s.get(STATUS_ROTULO_A1, "")) in ("true", "verdadeiro"),
                "ultima_execucao": s.get("Última execução com sucesso", ""),
                "resumo": s.get("Resumo da última execução", ""),
                "online": s.get("Robô online (último sinal)", ""),
                "comando": s.get("Comando", ""), "resposta": s.get("Resposta do robô", "")}


def criar_handler(estado, cfg, token, ultimo_uso):
    pc = socket.gethostname()
    hosts_ok = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}

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
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            if url.path == "/api/estado":
                dias = int(parse_qs(url.query).get("dias", ["45"])[0] or 0)
                return self._json({
                    "agente": nome_do_agente(), "pc": pc, "erro": estado.erro,
                    "atualizado_em": estado.atualizado_em.isoformat(timespec="seconds") if estado.atualizado_em else "",
                    "atualizar_segundos": int(cfg.get("app", {}).get("atualizar_segundos", 15)),
                    "status": estado.resumo_status(), "fila": estado.fila(dias),
                })
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
                    if not nome:
                        return self._json({"ok": False, "motivo": "nome vazio"}, 400)
                    salvar_json(CAMINHO_PREFS, {"agente": nome})
                    return self._json({"ok": True})
                if path == "/api/enviar":
                    quando = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
                    escrever_linhas_status(estado.backend, cfg, {LINHA_COMANDO: "ENVIAR",
                                                                 LINHA_PEDIDO: f"{nome_do_agente()} (app) | {quando}"})
                    return self._json({"ok": True})
                if path == "/api/atualizar":
                    estado.atualizar()
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
    if not porta_livre():
        if not sem_janela:
            abrir_janela()
        return 0

    from sheets import BackendGoogle
    cfg = carregar_config()
    estado = Estado(BackendGoogle(caminho_chave_google(cfg)), cfg)
    token = secrets.token_urlsafe(24)
    ultimo_uso = [time.monotonic()]
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), criar_handler(estado, cfg, token, ultimo_uso))
    intervalo = int(cfg.get("app", {}).get("atualizar_segundos", 15))

    def laco():   # primeira leitura já aqui: a janela abre sem esperar a planilha
        while True:
            estado.atualizar()
            time.sleep(intervalo)
            if not sem_janela and time.monotonic() - ultimo_uso[0] > FECHAR_SEM_USO_SEGUNDOS:
                logger.info("App fechado (janela sem uso) — encerrando o servidor.")
                servidor.shutdown()
                return

    threading.Thread(target=laco, daemon=True).start()
    logger.info(f"🖥️ Painel Notas Fiscais no ar em http://127.0.0.1:{PORTA}/ · agente {nome_do_agente()}")
    if not sem_janela:
        abrir_janela()
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
