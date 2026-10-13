"""Leitura e validação do config.json (+ config.local.json por PC)."""
import json
import os
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_CONFIG = PASTA_PROJETO / "config.json"
CAMINHO_CONFIG_LOCAL = PASTA_PROJETO / "config.local.json"
PASTA_ESTADO = PASTA_PROJETO / "estado"
PASTA_SIMULACAO = PASTA_PROJETO / "saida_simulacao"
PASTA_LOGS = PASTA_PROJETO / "logs"
CAMINHO_MAQUINA = PASTA_ESTADO / "maquina.json"

MODOS_VALIDOS = ("SIMULACAO", "TESTE", "PRODUCAO")


class ErroDeConfig(Exception):
    pass


def carregar_config(caminho=CAMINHO_CONFIG):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise ErroDeConfig(f"Não achei o arquivo de configuração: {caminho}")
    except json.JSONDecodeError as e:
        raise ErroDeConfig(f"config.json com erro de digitação (linha {e.lineno}, coluna {e.colno}): {e.msg}. "
                           f"Confira vírgulas e aspas perto dessa linha.")
    if Path(caminho) == CAMINHO_CONFIG:
        _mesclar(cfg, _ler_local())
    dropbox = cfg.get("dropbox_notas") or {}
    if dropbox.get("pastas"):   # %USERPROFILE% vira a pasta do usuário de cada PC
        dropbox["pastas"] = [os.path.expandvars(p) for p in dropbox["pastas"]]
    if "papel" not in cfg:
        cfg["papel"] = _papel_pela_identidade(cfg)
    validar_config(cfg)
    return cfg


def _papel_pela_identidade(cfg):
    try:
        with open(CAMINHO_MAQUINA, "r", encoding="utf-8") as f:
            maquina = json.load(f)
    except (FileNotFoundError, ValueError):
        return "conferente"
    import socket
    if maquina.get("pc") and maquina["pc"].lower() != socket.gethostname().lower():
        return "conferente"   # maquina.json de outro PC: na dúvida, nunca principal
    agente, principal = maquina.get("agente"), cfg.get("agente_principal")
    if agente and principal and not maquina.get("conflito") and _norm(agente) == _norm(principal):
        return "principal"
    return "conferente"


def _norm(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").strip().lower()


def _ler_local():
    try:
        with open(CAMINHO_CONFIG_LOCAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ErroDeConfig(f"config.local.json com erro (linha {e.lineno}): {e.msg}")


def _mesclar(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v


def e_principal(cfg):
    """Só o principal copia, envia e atende o menu; os conferentes só marcam as tags."""
    return cfg.get("papel") == "principal"


def validar_config(cfg):
    problemas = []

    modo = str(cfg.get("modo", "")).strip().upper()
    if modo not in MODOS_VALIDOS:
        problemas.append(f"'modo' precisa ser um destes: {', '.join(MODOS_VALIDOS)} (está '{cfg.get('modo')}').")
    cfg["modo"] = modo

    if modo == "TESTE" and "@" not in str(cfg.get("email_teste", "")):
        problemas.append("Modo TESTE precisa de um 'email_teste' preenchido.")

    if not str(cfg.get("planilha_central_id", "")).strip():
        problemas.append("'planilha_central_id' está vazio.")

    try:
        limite = int(cfg.get("limite_solicitacoes_por_email", 0))
        if limite < 1:
            raise ValueError
        cfg["limite_solicitacoes_por_email"] = limite
    except (TypeError, ValueError):
        problemas.append("'limite_solicitacoes_por_email' precisa ser um número maior que zero.")

    if str(cfg.get("formato_data_planilha", "")).lower() not in ("americano", "brasileiro"):
        problemas.append("'formato_data_planilha' precisa ser 'americano' ou 'brasileiro'.")

    caminho_chave = caminho_chave_google(cfg)
    if not caminho_chave or not os.path.exists(caminho_chave):
        problemas.append(f"Não achei a chave do Google em '{caminho_chave}'. "
                         f"Veja Segundo Cérebro\\6 Documentos\\Instalação e pendências.md (seção 7, a chave do Google).")

    for chave in ("enviado", "carimbo"):
        if not str(cfg.get("colunas", {}).get(chave, "")).strip():
            problemas.append(f"'colunas.{chave}' está vazio.")

    cfg.setdefault("outlook", {})
    cfg["outlook"].setdefault("tentativas_conexao", 5)
    cfg["outlook"].setdefault("espera_entre_tentativas_segundos", 60)
    cfg["outlook"].setdefault("espera_confirmacao_envio_segundos", 180)
    cfg.setdefault("colunas_ocultas", [])
    cfg.setdefault("registro_central", {"ativo": False})

    if problemas:
        raise ErroDeConfig("Problemas no config.json:\n  - " + "\n  - ".join(problemas))


def caminho_chave_google(cfg):
    return os.path.expandvars(str(cfg.get("caminho_chave_google", "")).strip())


if __name__ == "__main__":   # Bat\TESTAR_CONFIG.bat
    import sys
    try:
        c = carregar_config()
    except ErroDeConfig as e:
        print(f"❌ {e}")
        sys.exit(1)
    print("✅ config.json OK")
    print(f"   Modo: {c['modo']}")
    print(f"   E-mail de teste: {c.get('email_teste') or '(vazio)'}")
    print(f"   Conta remetente: {c.get('conta_remetente') or '(conta padrão do Outlook)'}")
    print(f"   Limite por e-mail: {c['limite_solicitacoes_por_email']}")
