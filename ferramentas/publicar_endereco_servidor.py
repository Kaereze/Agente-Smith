"""Publica o endereço (IP) deste PC, o "Servidor RA", numa aba do Google para os outros PCs acharem o servidor se o IP mudar.

    pythonw ferramentas\\publicar_endereco_servidor.py [--porta 8770] [--pasta C:\\ServidorCentral] [--appdata C:\\Users\\X\\AppData\\Roaming]

É o que a tarefa agendada `ServidorCentral_Endereco` roda (Automacoes\\agendar_servidor_central.ps1), como SISTEMA, ao ligar o Windows.
Fica rodando: a cada 20 s olha o IP deste PC; se mudou, grava na aba `Servidor_Endereco` na hora; mesmo sem mudar, renova a cada
30 min (sinal de vida). Só publica se o servidor central DESTE PC está respondendo (senão apontaria os PCs para o nada). Cada PC, ao
perder o servidor, lê essa aba, confere que o endereço é o servidor de verdade e passa a usá-lo (central/descoberta.py).
Resultado em <pasta>\\endereco.log: só endereço e horário, nada de hóspede. Uma cópia só: se já há outra rodando, esta sai.
"""
import argparse
import datetime
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

PORTA_DA_TRAVA = 8771          # só para saber se já há outra cópia rodando (127.0.0.1, ninguém de fora enxerga)
VOLTA_SEGUNDOS = 20
SINAL_DE_VIDA = datetime.timedelta(minutes=30)
LOG_MAXIMO = 200 * 1024


def consultar_servidor_local(porta, tempo=4):
    """O servidor central deste PC -> o que /v1/saude diz ({"ok", "servidor_id", ...}), ou None se não respondeu."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/v1/saude", timeout=tempo) as r:   # nosec B310: o próprio PC
            dados = json.loads(r.read().decode("utf-8"))
        return dados if isinstance(dados, dict) and dados.get("ok") else None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def uma_volta(estado, google, central_id, porta, pc, agora, ip=None, saude=None):
    """Uma olhada: publica se o endereço mudou ou se passou o tempo do sinal de vida. -> texto do que fez ("" = nada a fazer).
    `estado` é o que foi publicado por último ({"url", "servidor_id", "quando"}); é atualizado aqui."""
    from central import descoberta
    url = descoberta.endereco_da_lan(porta, ip)
    if not url:
        return "sem rede (ou IP que não é de rede privada): nada publicado"
    servidor_id = (saude or {}).get("servidor_id")
    if not servidor_id:
        return "o servidor central deste PC não respondeu: nada publicado"
    mudou = estado.get("url") != url or estado.get("servidor_id") != servidor_id
    velho = not estado.get("quando") or agora - estado["quando"] >= SINAL_DE_VIDA
    if not (mudou or velho):
        return ""
    google.substituir_aba(central_id, descoberta.ABA, descoberta.linhas_publicadas(url, servidor_id, pc, agora))
    estado.update(url=url, servidor_id=servidor_id, quando=agora)
    return f"publicado {url}" + (" (o endereço mudou)" if mudou else " (sinal de vida)")


def _anotar(pasta, texto):
    caminho = Path(pasta) / "endereco.log"
    try:
        if caminho.exists() and caminho.stat().st_size > LOG_MAXIMO:
            caminho.write_text("", encoding="utf-8")   # o log só serve para ver o que aconteceu há pouco
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--porta", type=int, default=8770)
    ap.add_argument("--pasta", default=r"C:\ServidorCentral")
    ap.add_argument("--appdata", default="", help="pasta AppData\\Roaming do usuário (onde está a chave do Google); só para rodar como SISTEMA")
    args = ap.parse_args(argv)
    if args.appdata:
        os.environ["APPDATA"] = args.appdata
    trava = socket.socket()
    try:
        trava.bind(("127.0.0.1", PORTA_DA_TRAVA))
    except OSError:
        return 0   # já há uma cópia rodando
    from central.sheets import BackendGoogle
    from config import caminho_chave_google, carregar_config
    cfg = carregar_config()
    google = BackendGoogle(caminho_chave_google(cfg))
    central, pc, estado = cfg["planilha_central_id"], socket.gethostname(), {}
    Path(args.pasta).mkdir(parents=True, exist_ok=True)
    _anotar(args.pasta, f"começou (PC {pc}, porta {args.porta})")
    while True:
        try:
            texto = uma_volta(estado, google, central, args.porta, pc, datetime.datetime.now(),
                              saude=consultar_servidor_local(args.porta))
            if texto:
                _anotar(args.pasta, texto)
            time.sleep(VOLTA_SEGUNDOS)
        except Exception as e:   # Google fora do ar etc.: anota e tenta de novo daqui a pouco (a leitura não depende disto)
            _anotar(args.pasta, f"erro: {type(e).__name__}: {str(e)[:150]}")
            time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
