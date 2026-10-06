"""Descobre de qual agente é este PC votando com as contas do Outlook contra o Cadastro_Hoteis.

    python src\\identidade.py
"""
import datetime
import json
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arquivos import salvar_json
from config import CAMINHO_MAQUINA, carregar_config, caminho_chave_google
from log_util import configurar_logging
from tratamento import normalizar

logger = configurar_logging(__name__)

# Na dúvida, não atribui.
MINIMO_CONTAS = 5        # perfil ainda carregando costuma mostrar só 1-2 contas
MAIORIA = 0.80
VANTAGEM = 5             # com poucas contas a porcentagem sozinha engana


def apurar(contas, cadastro):
    """{agente: votos}; cada conta vota uma vez, na primeira linha do cadastro com o e-mail dela."""
    contas = {c.strip().lower() for c in contas if c}
    voto = {}
    for _hotel, email, agente in cadastro:
        email = (email or "").strip().lower()
        if agente and email in contas:
            voto.setdefault(email, agente.strip())
    votos = {}
    for agente in voto.values():
        votos[agente] = votos.get(agente, 0) + 1
    return votos


def resolver(contas, cadastro):
    """-> (agente | None, confiança %, motivo, retentável)"""
    votos = apurar(contas, cadastro)
    total = sum(votos.values())
    ranking = sorted(votos.items(), key=lambda kv: kv[1], reverse=True)
    logger.info(f"🪪 Identidade: {len(contas)} conta(s) no Outlook, {total} no Cadastro_Hoteis · "
                + (" | ".join(f"{a}: {n}" for a, n in ranking) or "nenhum voto"))
    if total < MINIMO_CONTAS:
        return None, 0, f"só {total} conta(s) reconhecida(s) (mínimo {MINIMO_CONTAS}) — Outlook ainda carregando?", True
    agente, n = ranking[0]
    segundo = ranking[1][1] if len(ranking) > 1 else 0
    if n / total < MAIORIA:
        return None, 0, f"'{agente}' tem só {n / total:.0%} das contas — parece PC com contas de mais de um agente", False
    if n - segundo < VANTAGEM:
        return None, 0, f"'{agente}' venceu por só {n - segundo} conta(s) de vantagem", False
    return agente, round(100 * n / total), "ok", False


def detectar(cfg, namespace, backend):
    """Detecta e grava em estado/maquina.json; com voto claro, as contas do Outlook vencem o arquivo."""
    contas = [str(getattr(c, "SmtpAddress", "") or "") for c in namespace.Accounts]
    aba = cfg["aba_cadastro_hoteis"]
    linhas = backend.ler_abas(cfg["planilha_central_id"], [aba])[0].get(aba, [])
    col = cfg.get("cadastro_colunas", {})
    i_h, i_e, i_a = (ord(col.get(k, d).upper()) - 65 for k, d in (("hotel", "A"), ("email_hotel", "B"), ("agente", "C")))
    cadastro = [(l[i_h] if len(l) > i_h else "", l[i_e] if len(l) > i_e else "", l[i_a] if len(l) > i_a else "")
                for l in linhas if l and normalizar(l[i_a] if len(l) > i_a else "") not in ("", "agente", "operador")]
    agente, confianca, motivo, retentavel = resolver(contas, cadastro)
    anterior = ler()
    pc = socket.gethostname()
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    if agente is None:
        logger.warning(f"⚠️ Não consegui identificar este PC: {motivo}")
        if retentavel or anterior:
            return anterior or {}
        dados = {"agente": None, "motivo": motivo, "pc": pc, "quando": agora}
    else:
        # maquina.json copiado de outro PC (ou troca de operador): o voto claro das contas manda
        if anterior.get("agente") and anterior["agente"] != agente:
            logger.warning(f"🔄 Identidade corrigida: estado\\maquina.json dizia '{anterior['agente']}', "
                           f"mas as contas do Outlook são do(a) '{agente}' ({confianca}%).")
        elif not anterior.get("agente"):
            logger.info(f"🆕 Este PC é do(a) {agente} ({confianca}% de confiança).")
        dados = {"agente": agente, "confianca": confianca, "contas": len(contas), "pc": pc, "quando": agora}
    salvar_json(CAMINHO_MAQUINA, dados)
    return dados


def ler():
    """maquina.json deste PC; o de outro PC (pasta estado\\ copiada) conta como inexistente."""
    try:
        dados = json.load(open(CAMINHO_MAQUINA, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    if dados.get("pc") and dados["pc"].lower() != socket.gethostname().lower():
        return {}
    return dados


if __name__ == "__main__":
    import win32com.client
    from sheets import BackendGoogle
    cfg = carregar_config()
    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    dados = detectar(cfg, ns, BackendGoogle(caminho_chave_google(cfg), somente_leitura=True))
    print(f"\nEste PC: {dados.get('agente') or '(não identificado)'}"
          + (f" · CONFLITO: {dados['conflito']}" if dados.get("conflito") else "")
          + f"\nPapel: {carregar_config()['papel']}  (principal = agente '{cfg.get('agente_principal')}')")
