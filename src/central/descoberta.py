"""Como os PCs acham o servidor central quando o endereço (IP) dele muda (API central, 25/11/2026).

O IP do notebook "Servidor RA" vem do DHCP do escritório e pode mudar. Sem isto, trocou o IP, todos os PCs perdem o servidor até
alguém mandar `ligar_servidor` com o número novo. Com isto, o caminho é automático:

1. o notebook ANOTA o próprio endereço numa aba pequena do Google, `Servidor_Endereco` (só grava quando muda, mais um sinal de vida
   a cada 30 min; ferramentas/publicar_endereco_servidor.py). A aba mora no Google de propósito, como o `Comandos_PC`: é o único
   lugar que não depende de saber o endereço do servidor;
2. cada PC, quando o servidor não responde, lê essa aba (e o `estado/central_api.json`, que outro programa do mesmo PC pode já ter
   corrigido), CONFERE que o endereço novo é o servidor de verdade e só então passa a usá-lo (BackendAPI, central/backend_api.py).

A conferência é o que impede um aparelho qualquer, que tenha herdado o IP velho, de receber os dados: o servidor responde a um
desafio com uma prova que só quem tem o token sabe calcular (o token nunca viaja nessa conferência), e o identificador do banco
tem que ser o mesmo que o PC guardou quando foi ligado. Só vale endereço da rede do escritório (IP privado ou nome de PC sem ponto).
"""
import datetime
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from sistema import armazem

ABA = "Servidor_Endereco"
CABECALHO = ["Endereço do servidor", "Identificador do servidor", "PC", "Atualizado em"]
PORTA_PADRAO = 8770
_NOME_DE_REDE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")   # nome simples de PC, sem ponto (nada da internet)


def url_valida(texto):
    """-> (url limpa, "") ou ("", motivo). Só http, só a rede do escritório (IP privado, o próprio PC ou nome de PC sem ponto) e porta."""
    url = str(texto or "").strip().rstrip("/")
    try:
        partes = urlparse(url)
        porta = partes.port
    except ValueError:
        return "", "endereço inválido"
    if partes.scheme != "http" or not partes.hostname or not porta or partes.path not in ("", "/") or partes.username:
        return "", "use o formato http://IP:porta (ex.: http://10.0.0.5:8770)"
    host = partes.hostname
    try:
        ip = ipaddress.ip_address(host)
        if not (ip.is_private or ip.is_loopback):
            return "", "o servidor central tem que estar na rede do escritório (IP privado), não na internet"
    except ValueError:
        if not _NOME_DE_REDE.match(host):
            return "", "o nome do servidor deve ser o de um PC da rede (sem ponto)"
    return f"http://{host}:{porta}", ""


# ---------------------------------------------------------------- o que o notebook (servidor) publica
def ip_da_lan():
    """O IP que este PC usa na rede do escritório agora ("" se está sem rede). Não manda nada: só pergunta ao Windows por qual
    placa sairia um pacote para fora (assim ignora placas virtuais e o 127.0.0.1)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.254", 9))
            return s.getsockname()[0]
    except OSError:
        return ""


def endereco_da_lan(porta=PORTA_PADRAO, ip=None):
    """http://IP-DESTE-PC:porta, ou "" se não há rede ou o IP não é de rede privada."""
    ip = ip_da_lan() if ip is None else ip
    return url_valida(f"http://{ip}:{porta}")[0] if ip else ""


def linhas_publicadas(url, servidor_id, pc, agora=None):
    agora = agora or datetime.datetime.now()
    return [list(CABECALHO), [url, servidor_id, pc, agora.isoformat(timespec="seconds")]]


def ler_publicado(linhas):
    """As linhas da aba -> {"url", "servidor_id", "pc", "atualizado_em"}, ou None se não há endereço válido."""
    if not linhas or len(linhas) < 2:
        return None
    linha = list(linhas[1]) + [""] * 4
    url, _ = url_valida(linha[0])
    if not url:
        return None
    return {"url": url, "servidor_id": str(linha[1]).strip(), "pc": str(linha[2]).strip(), "atualizado_em": str(linha[3]).strip()}


# ---------------------------------------------------------------- conferir que o endereço é o servidor de verdade
def prova_do_desafio(token, desafio):
    """A mesma conta do servidor (servidor_central/servidor.py; está nos dois lados de propósito: o servidor roda sozinho, sem o resto do
    projeto, no Docker). Um teste garante que as duas dão o mesmo resultado."""
    chave = token if isinstance(token, bytes) else str(token).encode("utf-8")
    return hmac.new(chave, b"prova-do-servidor-v1|" + desafio.encode("utf-8"), hashlib.sha256).hexdigest()


def verificar_servidor(url, token, servidor_id="", tempo=4):
    """O endereço é mesmo o nosso servidor? -> (ok, motivo). Nunca manda o token: manda um desafio e confere a prova. Se `servidor_id`
    foi dado, o banco tem que ser o mesmo (outro servidor, mesmo com a chave certa, não vale)."""
    desafio = secrets.token_hex(8)
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/v1/saude?desafio={desafio}", timeout=tempo) as r:   # nosec B310: endereço da rede do escritório
            resposta = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return False, f"não respondeu ({str(e)[:80]})"
    if not isinstance(resposta, dict) or not resposta.get("ok"):
        return False, "resposta inesperada"
    if not hmac.compare_digest(str(resposta.get("prova") or ""), prova_do_desafio(token, desafio)):
        return False, "não provou conhecer a senha do servidor"
    if servidor_id and resposta.get("servidor_id") != servidor_id:
        return False, "é outro servidor (identificador diferente)"
    return True, "ok"


def identificador_do_servidor(url, tempo=4):
    """O identificador do banco que atende neste endereço ("" se não respondeu). Quem liga um PC no servidor guarda este número."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/v1/saude", timeout=tempo) as r:   # nosec B310: endereço da rede do escritório
            return str(json.loads(r.read().decode("utf-8")).get("servidor_id") or "")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------- o que cada PC guarda
def _caminho():
    return armazem.caminho("central_api.json")


def endereco_local():
    """O endereço que o `estado/central_api.json` deste PC tem agora ("" se não há)."""
    try:
        with open(_caminho(), encoding="utf-8") as f:
            return str(json.load(f).get("url") or "").strip()
    except (OSError, ValueError, AttributeError):
        return ""


def guardar_endereco(url):
    """Troca só o endereço no arquivo deste PC (o resto fica: ligada, token, identificador). Vale para todos os programas deste PC."""
    caminho = _caminho()
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(dados, dict):
        return False
    dados["url"] = url
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados), encoding="utf-8")
    temporario.replace(caminho)
    return True


class DescobertaPeloGoogle:
    """O que o `BackendAPI` usa para achar o servidor de novo: o arquivo local e a aba `Servidor_Endereco` do Google."""

    def __init__(self, google, central_id):
        self._google, self._central = google, central_id

    def endereco_local(self):
        return endereco_local()

    def endereco_publicado(self):
        """-> {"url", "servidor_id", ...} ou None. Uma leitura do Google."""
        lidas, _erros = self._google.ler_abas(self._central, [ABA])
        return ler_publicado(lidas.get(ABA))

    def guardar_endereco(self, url):
        return guardar_endereco(url)
