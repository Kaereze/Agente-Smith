"""Identidade do PC: descobre o agente pelas contas do Outlook × Cadastro_Hoteis (lógica do Mail Analytics).
Uso: python src\\identidade.py  (mostra quem é este PC)
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arquivos import salvar_json
from config import CAMINHO_MAQUINA, carregar_config, caminho_chave_google
from log_util import configurar_logging
from tratamento import normalizar

logger = configurar_logging(__name__)

# Travas da votação (mesmas do Mail Analytics): na dúvida, recusa — nunca chuta
MINIMO_CONTAS = 5        # perfil do Outlook carregando pode mostrar só 1-2 contas
MAIORIA = 0.80           # contas de mais de um agente no mesmo PC = não atribui
VANTAGEM = 5             # poucas contas deixam a porcentagem enganosa


def apurar(contas, cadastro):
    """{agente: votos} — cada conta do Outlook vota 1 vez (a 1ª linha do cadastro com o e-mail dela decide)."""
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
    """(agente | None, confiança %, motivo, retentável)."""
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
    """Detecta, compara com o que este PC já sabia (estado/maquina.json) e grava. Devolve o dict gravado."""
    contas = [str(getattr(c, "SmtpAddress", "") or "") for c in namespace.Accounts]
    aba = cfg["aba_cadastro_hoteis"]
    linhas = backend.ler_abas(cfg["planilha_central_id"], [aba])[0].get(aba, [])
    col = cfg.get("cadastro_colunas", {})
    i_h, i_e, i_a = (ord(col.get(k, d).upper()) - 65 for k, d in (("hotel", "A"), ("email_hotel", "B"), ("agente", "C")))
    cadastro = [(l[i_h] if len(l) > i_h else "", l[i_e] if len(l) > i_e else "", l[i_a] if len(l) > i_a else "")
                for l in linhas if l and normalizar(l[i_a] if len(l) > i_a else "") not in ("", "agente", "operador")]
    agente, confianca, motivo, retentavel = resolver(contas, cadastro)
    anterior = ler()
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    if agente is None:
        logger.warning(f"⚠️ Não consegui identificar este PC: {motivo}")
        if retentavel or anterior:
            return anterior or {}
        dados = {"agente": None, "motivo": motivo, "quando": agora}
    elif anterior.get("agente") and anterior["agente"] != agente:
        motivo = f"este PC era '{anterior['agente']}' e agora parece '{agente}' — apague estado\\maquina.json se a troca for de propósito"
        logger.error(f"🚨 CONFLITO DE IDENTIDADE: {motivo}")
        dados = {**anterior, "conflito": motivo, "quando": agora}
    else:
        dados = {"agente": agente, "confianca": confianca, "contas": len(contas), "quando": agora}
        if not anterior.get("agente"):
            logger.info(f"🆕 Este PC é do(a) {agente} ({confianca}% de confiança).")
    salvar_json(CAMINHO_MAQUINA, dados)
    return dados


def ler():
    try:
        return json.load(open(CAMINHO_MAQUINA, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


if __name__ == "__main__":
    import win32com.client
    from sheets import BackendGoogle
    cfg = carregar_config()
    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    dados = detectar(cfg, ns, BackendGoogle(caminho_chave_google(cfg), somente_leitura=True))
    print(f"\nEste PC: {dados.get('agente') or '(não identificado)'}"
          + (f" · CONFLITO: {dados['conflito']}" if dados.get("conflito") else "")
          + f"\nPapel: {carregar_config()['papel']}  (principal = agente '{cfg.get('agente_principal')}')")
