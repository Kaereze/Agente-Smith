"""Ligar e desligar o servidor central num PC, por comando (API central, etapa 5, 24/11/2026).

O João manda o comando pela aba Comandos_PC (que continua no Google de propósito: é o canal de volta se o servidor cair):

    ligar_servidor http://IP-DO-SERVIDOR:8770      -> este PC passa a usar o servidor
    desligar_servidor                              -> este PC volta para o Google

`ligar_servidor` NÃO liga a qualquer custo: antes confere que o endereço é da rede do escritório, que o servidor responde, que o
token (derivado da chave do Google do próprio PC) é aceito e que a Central já foi copiada para lá. Se algo falha, o PC fica como
estava e a resposta do comando diz o motivo. Funciona com `TODOS` (todos os PCs de uma vez), que é como a virada deve ser feita.

Aqui só se decide e se grava o arquivo `estado/central_api.json`; o reinício do Painel (e do conferente e do robô, que leem o
arquivo ao subir) é feito por quem chama.
"""
import datetime
import ipaddress
import json
import re
from urllib.parse import urlparse

from central import backend_roteado
from central.backend_api import BackendAPI
from rede import rede_pcs

COMANDO_LIGAR = "ligar_servidor"
COMANDO_DESLIGAR = "desligar_servidor"
COMANDOS_DA_VIRADA = frozenset({COMANDO_LIGAR, COMANDO_DESLIGAR})
ABAS_ESSENCIAIS = ("Envios_NF", "PCs_Painel", "Status")   # se o servidor não tem estas, a Central não foi copiada para lá
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


def conferir_servidor(url, cfg, api=None):
    """O servidor está pronto para este PC passar a usá-lo? -> (ok, texto)"""
    if api is None:
        token = backend_roteado.token_derivado(cfg)
        if not token:
            return False, "este PC não tem a chave do Google para calcular o token do servidor"
        api = BackendAPI(url, token, tempo=15)
    try:
        abas = api.listar_abas(cfg["planilha_central_id"])
    except Exception as e:
        return False, f"o servidor não respondeu ({str(e)[:120]})"
    faltam = [a for a in ABAS_ESSENCIAIS if a not in abas]
    if faltam:
        return False, f"o servidor responde, mas a Central ainda não foi copiada para lá (faltam: {', '.join(faltam)})"
    return True, f"servidor pronto ({len(abas)} abas)"


def ligar(url_pedida, cfg, api=None):
    """Confere e grava o arquivo que liga este PC no servidor. -> (ok, texto para a resposta do comando)"""
    url, motivo = url_valida(url_pedida)
    if not url:
        return False, f"não liguei: {motivo}"
    ok, texto = conferir_servidor(url, cfg, api)
    if not ok:
        return False, f"não liguei: {texto}"
    _gravar({"ligada": True, "url": url})
    return True, f"ligado no servidor central {url} ({texto}); reiniciando"


def desligar():
    """Este PC volta para o Google (o arquivo fica, só desligado, guardando o endereço). -> (ok, texto)"""
    antes = {}
    try:
        with open(backend_roteado._caminho(), encoding="utf-8") as f:
            antes = json.load(f)
    except (OSError, ValueError):
        pass
    if not antes.get("ligada"):
        return True, "já estava no Google"
    _gravar({"ligada": False, "url": antes.get("url", "")})
    return True, "voltou para o Google; reiniciando"


def _gravar(dados):
    caminho = backend_roteado._caminho()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados), encoding="utf-8")
    temporario.replace(caminho)


def onde_estao(linhas_google, linhas_servidor, agora=None, segundos=None):
    """Cada PC está dando sinal de vida (PCs_Painel, coluna "Visto em") no Google, no servidor, nos dois ou em nenhum?
    Serve para a virada: um PC que perdeu o comando (estava desligado) continua no Google, isolado dos outros, sem ninguém notar.
    -> {pc: "servidor" | "google" | "os dois" | "desligado"}"""
    agora = agora or datetime.datetime.now()
    limite = datetime.timedelta(seconds=segundos or rede_pcs.PC_ONLINE_SEGUNDOS)

    def vistos(linhas):
        achados = {}
        for linha in (linhas or [])[1:]:
            linha = list(linha) + [""] * 4
            pc = str(linha[0]).strip()
            quando = rede_pcs._data(linha[3])
            if pc:
                achados[pc] = bool(quando and agora - quando <= limite)
        return achados
    g, s = vistos(linhas_google), vistos(linhas_servidor)
    resultado = {}
    for pc in sorted(set(g) | set(s)):
        no_g, no_s = g.get(pc, False), s.get(pc, False)
        resultado[pc] = "os dois" if no_g and no_s else "servidor" if no_s else "google" if no_g else "desligado"
    return resultado


def dividido(onde):
    """Há PC no servidor e PC no Google ao mesmo tempo? (cada grupo enxerga uma Central diferente)"""
    valores = set(onde.values())
    return "servidor" in valores and "google" in valores
