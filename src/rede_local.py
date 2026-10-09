"""Conversa direta entre os Painéis dos 4 PCs pela rede do escritório (os 4 ficam na mesma rede — usuário, 08/10/2026).

Serve pro que é ao vivo e não deve passar pela planilha (nem gastar cota do Google, nem ficar guardado):
  /rede/buscar   pesquisa no Outlook deste PC (hóspede, CPF, frase...)
  /rede/texto    texto inteiro de um e-mail das caixas deste PC
  /rede/ping     "estou aqui"
Segurança:
- Só aceita pedido de IP da rede local (10.x, 172.16-31.x, 192.168.x).
- Todo pedido vem assinado (HMAC) com um segredo tirado da chave do Google — só os 4 PCs do financeiro têm. A
  assinatura leva a hora: um pedido copiado da rede não serve de novo depois de 2 minutos.
- Só e-mail das caixas dos hotéis sai (nunca uma caixa pessoal), e só leitura: nada é mexido no Outlook.
O endereço de cada PC (ip:porta) vai na aba PCs_Painel.
"""
import hashlib
import hmac
import ipaddress
import json
import socket
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from log_util import configurar_logging

logger = configurar_logging("rede_local")

PORTA = 8766
VALIDADE_ASSINATURA = 120
TEMPO_RESPOSTA = 12
MAX_CORPO = 64 * 1024


def segredo_da_chave(caminho_chave):
    """Segredo comum aos 4 PCs, derivado da chave privada da conta de serviço (o arquivo nunca sai do PC)."""
    try:
        dados = json.load(open(caminho_chave, encoding="utf-8"))
        base = f"{dados.get('private_key_id', '')}|{dados.get('private_key', '')}"
    except (OSError, ValueError):
        return b""
    return hashlib.sha256(("painel-fiscal-rede|" + base).encode()).digest()


def assinar(segredo, quando, caminho, corpo):
    return hmac.new(segredo, f"{quando}\n{caminho}\n".encode() + corpo, hashlib.sha256).hexdigest()


def assinatura_ok(segredo, quando, caminho, corpo, assinatura, agora=None):
    if not segredo or not assinatura:
        return False
    try:
        if abs((agora or time.time()) - float(quando)) > VALIDADE_ASSINATURA:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(assinar(segredo, quando, caminho, corpo), assinatura)


def ip_da_rede_local(ip):
    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return endereco.is_private or endereco.is_loopback


def meu_ip():
    """IP deste PC na rede do escritório (não manda nada pra fora: só pergunta ao Windows qual placa sairia)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def endereco_deste_pc():
    return f"{meu_ip()}:{PORTA}"


class Servidor:
    """acoes: {"buscar": f(corpo) -> dict, "texto": f(corpo) -> dict, "ping": f(corpo) -> dict}"""

    def __init__(self, segredo, acoes, porta=PORTA):
        self.segredo, self.acoes, self.porta = segredo, acoes, porta
        self.http = None

    def iniciar(self):
        if not self.segredo:
            logger.warning("⚠️ Sem a chave do Google: a conversa pela rede entre os PCs fica desligada.")
            return False
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _responder(self, codigo, corpo):
                dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_POST(self):
                if not ip_da_rede_local(self.client_address[0]):
                    return self._responder(403, {"erro": "fora da rede"})
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > MAX_CORPO:
                    return self._responder(413, {"erro": "grande demais"})
                corpo = self.rfile.read(tamanho)
                if not assinatura_ok(servidor.segredo, self.headers.get("X-Quando", ""), self.path, corpo,
                                     self.headers.get("X-Assinatura", "")):
                    return self._responder(403, {"erro": "assinatura"})
                acao = servidor.acoes.get(self.path.removeprefix("/rede/"))
                if acao is None:
                    return self._responder(404, {"erro": "não encontrado"})
                try:
                    import pythoncom
                    pythoncom.CoInitialize()   # cada pedido roda numa thread: o Outlook (COM) precisa disso
                except ImportError:
                    pass
                try:
                    return self._responder(200, acao(json.loads(corpo or b"{}")))
                except PermissionError as e:
                    return self._responder(403, {"erro": str(e)})
                except Exception as e:
                    logger.warning(f"⚠️ Pedido da rede ({self.path}) falhou: {e}")
                    return self._responder(500, {"erro": str(e)[:200]})

        try:
            self.http = ThreadingHTTPServer(("0.0.0.0", self.porta), Handler)
        except OSError as e:
            logger.warning(f"⚠️ Não consegui abrir a porta {self.porta} pra rede dos PCs ({e})")
            return False
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        logger.info(f"🔗 Painel ouvindo os outros PCs em {endereco_deste_pc()}")
        return True


def perguntar(segredo, endereco, acao, corpo, tempo=TEMPO_RESPOSTA):
    """POST assinado pra outro PC. -> dict (ou levanta erro)."""
    caminho = f"/rede/{acao}"
    dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
    quando = f"{time.time():.3f}"
    pedido = urllib.request.Request(f"http://{endereco}{caminho}", data=dados, method="POST", headers={
        "Content-Type": "application/json", "X-Quando": quando, "X-Assinatura": assinar(segredo, quando, caminho, dados)})
    with urllib.request.urlopen(pedido, timeout=tempo) as r:
        return json.loads(r.read() or b"{}")


def perguntar_a_todos(segredo, enderecos, acao, corpo, tempo=TEMPO_RESPOSTA):
    """enderecos: {pc: "ip:porta"}. Pergunta em paralelo. -> {pc: resposta | {"erro": ...}}"""
    if not enderecos:
        return {}

    def um(pc_end):
        pc, end = pc_end
        try:
            return pc, perguntar(segredo, end, acao, corpo, tempo)
        except Exception as e:
            return pc, {"erro": f"não respondeu pela rede ({type(e).__name__})"}
    with ThreadPoolExecutor(max_workers=len(enderecos)) as ex:
        return dict(ex.map(um, enderecos.items()))
