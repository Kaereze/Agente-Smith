"""Conversa direta entre os Painéis dos 4 PCs pela rede do escritório (os 4 ficam na mesma rede — usuário, 08/10/2026).

Serve pro que é ao vivo e não deve passar pela planilha (nem gastar cota do Google, nem ficar guardado):
  /rede/buscar   pesquisa no Outlook deste PC (hóspede, CPF, frase...)
  /rede/texto    texto inteiro de um e-mail das caixas deste PC
  /rede/ping     "estou aqui"
  /rede/enviar   o robô (PC principal) pede: manda o e-mail do formulário da caixa do hotel que está neste Outlook,
                 para ela mesma (envio_pc_dono, 15/10/2026); /rede/conferir_envio: ele já está em Itens Enviados?
Segurança:
- Só aceita pedido de IP da rede local (10.x, 172.16-31.x, 192.168.x).
- Todo pedido vem assinado (HMAC) com um segredo tirado da chave do Google — só os 4 PCs do financeiro têm. A
  assinatura leva a hora e um código único: um pedido copiado da rede não serve de novo (o código só vale uma vez)
  e perde a validade em 30 s (Fase 1 do plano, 05/11/2026).
- O conteúdo do pedido e da resposta vai cifrado (AES-GCM, Fase 2, 05/11/2026); detalhes perto de `cifrar`.
- Teto de tamanho do pedido, tempo-limite de leitura por conexão (quem fica parado é cortado) e Content-Length
  inválido é recusado.
- Só e-mail das caixas dos hotéis sai (nunca uma caixa pessoal). Fora o /rede/enviar, só leitura; e o /rede/enviar
  só manda o e-mail do robô (código NF-) da caixa do hotel para ela mesma, nunca para fora.
O endereço de cada PC (ip:porta) vai na aba PCs_Painel.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from log_util import configurar_logging
import ajustes

logger = configurar_logging("rede_local")

PORTA = 8766
VALIDADE_ASSINATURA = ajustes.valor("rede.assinatura_validade_segundos")
TEMPO_RESPOSTA = ajustes.valor("rede.resposta_maxima_segundos")
MAX_CORPO = ajustes.valor("rede.corpo_maximo_mb") * 1024 * 1024   # o /rede/enviar leva o HTML do e-mail (até ~40 KB)
TEMPO_LEITURA = 10   # segundos que uma conexão pode ficar parada antes de o servidor largar (pedido lento não prende o Painel)


ARQUIVO_SEGREDO_REDE = "segredo-rede.txt"


def _segredo_do_arquivo(caminho_chave):
    """Segredo da rede guardado à parte (29/10/2026): 64 caracteres hexadecimais em segredo-rede.txt, na mesma pasta da chave.
    Serve para um PC com chave do Google diferente (chave nova, criada só para ele) falar com os outros sem a chave privada
    de ninguém viajar: o arquivo leva só o resumo já calculado. Arquivo ausente ou malformado = None (vale o cálculo da chave)."""
    try:
        texto = (Path(caminho_chave).parent / ARQUIVO_SEGREDO_REDE).read_text(encoding="utf-8").strip()
        segredo = bytes.fromhex(texto)
    except (OSError, ValueError):
        return None
    return segredo if len(segredo) == 32 else None


def _segredo_calculado(caminho_chave):
    try:
        dados = json.load(open(caminho_chave, encoding="utf-8"))
        base = f"{dados.get('private_key_id', '')}|{dados.get('private_key', '')}"
    except (OSError, ValueError):
        return b""
    return hashlib.sha256(("painel-fiscal-rede|" + base).encode()).digest()


def segredo_da_chave(caminho_chave):
    """Segredo comum aos PCs da rede. Vale o segredo-rede.txt ao lado da chave, se existir; senão é derivado da chave privada
    da conta de serviço (o arquivo nunca sai do PC). O resultado dos dois é o mesmo número para quem tem a chave original."""
    return _segredo_do_arquivo(caminho_chave) or _segredo_calculado(caminho_chave)


def gerar_arquivo_segredo(caminho_chave, destino):
    """Grava em destino o segredo calculado da chave de caminho_chave (para levar a um PC com outra chave). Nunca mostra o
    valor. -> True se gravou."""
    segredo = _segredo_calculado(caminho_chave)
    if not segredo:
        return False
    Path(destino).write_text(segredo.hex(), encoding="utf-8")
    return True


def assinar(segredo, quando, caminho, corpo, codigo=""):
    if not codigo:   # formato antigo (PC ainda na versão anterior): continua igual, para as duas versões se entenderem
        return hmac.new(segredo, f"{quando}\n{caminho}\n".encode() + corpo, hashlib.sha256).hexdigest()
    return hmac.new(segredo, f"{quando}\n{caminho}\n{codigo}\n".encode() + corpo, hashlib.sha256).hexdigest()


class CodigosUsados:
    """Guarda os códigos já vistos pelo tempo em que a assinatura ainda valeria: o mesmo pedido copiado da rede é recusado."""

    def __init__(self, validade=None, relogio=time.time):
        self.validade, self.relogio = validade or VALIDADE_ASSINATURA, relogio
        self._vistos, self._trava = {}, threading.Lock()

    def usar(self, codigo):
        """-> True se o código é novo (e fica anotado); False se vazio, malformado ou repetido."""
        if not isinstance(codigo, str) or not 16 <= len(codigo) <= 64:
            return False
        agora = self.relogio()
        with self._trava:
            for velho in [c for c, t in self._vistos.items() if agora - t > 2 * self.validade]:
                del self._vistos[velho]
            if codigo in self._vistos:
                return False
            self._vistos[codigo] = agora
            return True


def assinatura_ok(segredo, quando, caminho, corpo, assinatura, agora=None, codigo=""):
    if not segredo or not assinatura:
        return False
    try:
        if abs((agora or time.time()) - float(quando)) > VALIDADE_ASSINATURA:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(assinar(segredo, quando, caminho, corpo, codigo), assinatura)


# ---------- cifra do conteúdo (Fase 2, 05/11/2026) ----------
# O texto de e-mail e o CPF passavam abertos na rede do escritório. Agora o corpo do pedido e da resposta vai cifrado
# (AES-256-GCM, chave tirada do segredo da rede). A assinatura continua valendo. PC sem a biblioteca `cryptography`
# segue falando como antes (aberto, assinado). EXIGIR_CIFRA fica desligado até os 4 PCs estarem na versão nova;
# depois é só trocar para True e a rede recusa pedido aberto.
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:   # pragma: no cover - depende de como o PC foi instalado
    AESGCM = None
CIFRA_DISPONIVEL = AESGCM is not None
EXIGIR_CIFRA = False
EXIGIR_CODIGO = False   # idem para o código único; com False, pedido do formato antigo ainda passa (e não pode ser repetido)
_PCS_SEGUROS = set()   # endereços que já provaram falar o formato novo (resposta com X-Seguro); só a eles se manda cifrado


def _chave_de_cifra(segredo):
    return hashlib.sha256(b"painel-fiscal-cifra|" + segredo).digest()


def cifrar(segredo, dados, associado):
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(_chave_de_cifra(segredo)).encrypt(nonce, dados, associado)


def decifrar(segredo, dados, associado):
    """-> bytes, ou levanta ValueError se foi adulterado, veio com outro segredo ou está curto demais."""
    if len(dados) < 12 + 16:
        raise ValueError("curto demais")
    try:
        return AESGCM(_chave_de_cifra(segredo)).decrypt(dados[:12], dados[12:], associado)
    except Exception as e:
        raise ValueError("não decifrou") from e


def _associado_pedido(quando, caminho, codigo):
    return f"{quando}|{caminho}|{codigo}".encode()


def _associado_resposta(codigo):
    return f"resposta|{codigo}".encode()


def gerar_segredo_novo(destino):
    """Grava em destino um segredo novo, aleatório e independente da chave do Google (Fase 2). O mesmo arquivo
    (segredo-rede.txt) precisa ir para a pasta da chave dos 4 PCs; sem ele, vale o segredo derivado da chave. Nunca mostra o valor."""
    Path(destino).write_text(secrets.token_hex(32), encoding="utf-8")
    return True


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
        self.codigos = CodigosUsados()

    def iniciar(self):
        if not self.segredo:
            logger.warning("⚠️ Sem a chave do Google: a conversa pela rede entre os PCs fica desligada.")
            return False
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            timeout = TEMPO_LEITURA

            def log_message(self, *_):
                pass

            def _responder(self, codigo, corpo, cifrar_para=None):
                dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
                self.send_response(codigo)
                self.send_header("X-Seguro", "1")   # "falo o formato novo": quem pergunta passa a mandar cifrado e com código
                if cifrar_para:   # resposta cifrada para o pedido que veio cifrado (Fase 2)
                    dados = cifrar(servidor.segredo, dados, _associado_resposta(cifrar_para))
                    self.send_header("X-Cifrado", "1")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_POST(self):
                if not ip_da_rede_local(self.client_address[0]):
                    return self._responder(403, {"erro": "fora da rede"})
                try:
                    tamanho = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    tamanho = -1
                if tamanho < 0:
                    return self._responder(400, {"erro": "tamanho inválido"})
                if tamanho > MAX_CORPO:
                    return self._responder(413, {"erro": "grande demais"})
                corpo = self.rfile.read(tamanho)
                codigo = self.headers.get("X-Codigo", "")
                if not assinatura_ok(servidor.segredo, self.headers.get("X-Quando", ""), self.path, corpo,
                                     self.headers.get("X-Assinatura", ""), codigo=codigo):
                    return self._responder(403, {"erro": "assinatura"})
                if not codigo and EXIGIR_CODIGO:
                    return self._responder(403, {"erro": "código ausente"})
                # formato antigo: a própria assinatura (única por pedido) serve de código para barrar a cópia
                if not servidor.codigos.usar(codigo or self.headers.get("X-Assinatura", "")):
                    return self._responder(403, {"erro": "código repetido ou ausente"})
                cifrado = self.headers.get("X-Cifrado") == "1"
                if not cifrado and EXIGIR_CIFRA:
                    return self._responder(403, {"erro": "pedido sem cifra"})
                if cifrado:
                    if not CIFRA_DISPONIVEL:
                        return self._responder(501, {"erro": "este PC não tem a biblioteca de cifra"})
                    try:
                        corpo = decifrar(servidor.segredo, corpo, _associado_pedido(self.headers.get("X-Quando", ""), self.path, codigo))
                    except ValueError:
                        return self._responder(403, {"erro": "cifra"})
                acao = servidor.acoes.get(self.path.removeprefix("/rede/"))
                if acao is None:
                    return self._responder(404, {"erro": "não encontrado"})
                try:
                    import pythoncom
                    pythoncom.CoInitialize()   # cada pedido roda numa thread: o Outlook (COM) precisa disso
                except ImportError:
                    pass
                try:
                    return self._responder(200, acao(json.loads(corpo or b"{}")), cifrar_para=codigo if cifrado else None)
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
    cabecalhos = {"Content-Type": "application/json", "X-Quando": quando}
    seguro = CIFRA_DISPONIVEL and endereco in _PCS_SEGUROS   # o 1º pedido a um PC vai no formato antigo, que as duas versões entendem
    if seguro:
        codigo = secrets.token_hex(16)
        dados = cifrar(segredo, dados, _associado_pedido(quando, caminho, codigo))
        cabecalhos.update({"X-Codigo": codigo, "X-Cifrado": "1"})
    else:
        codigo = ""
    cabecalhos["X-Assinatura"] = assinar(segredo, quando, caminho, dados, codigo)
    pedido = urllib.request.Request(f"http://{endereco}{caminho}", data=dados, method="POST", headers=cabecalhos)
    with urllib.request.urlopen(pedido, timeout=tempo) as r:
        if r.headers.get("X-Seguro") == "1":
            _PCS_SEGUROS.add(endereco)
        resposta = r.read() or b"{}"
        if r.headers.get("X-Cifrado") == "1":
            resposta = decifrar(segredo, resposta, _associado_resposta(codigo))
        return json.loads(resposta)


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
