"""Deixa este PC no papel "só Painel" (29/10/2026): sem Outlook, sem caixas de hotel. Chamado pelo instalador.

    .venv\\Scripts\\python.exe Automacoes\\configurar_pc_so_painel.py Ingrid

Grava, só neste PC (nada disso vai para o GitHub):
  config.local.json   papel "so_painel", o operador na lista de agentes e, se o Dropbox das notas não existe aqui, a leitura dele desligada
  estado\\app.json     quem está usando este Painel (o nome que aparece nos pedidos de envio)
Roda quantas vezes quiser: só soma ao que já existe.
"""
import json
import os
import sys
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent


def _ler(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def dropbox_existe(cfg):
    pastas = (cfg.get("dropbox_notas") or {}).get("pastas") or []
    return any(os.path.isdir(os.path.expandvars(p)) for p in pastas)


def preparar(operador, pasta_projeto=PASTA_PROJETO):
    """-> {"operador", "papel", "dropbox"} do que ficou valendo."""
    operador = str(operador or "").strip()
    if not operador:
        raise ValueError("Diga o nome do operador (ex.: Ingrid).")
    pasta_projeto = Path(pasta_projeto)
    local_caminho = pasta_projeto / "config.local.json"
    local = _ler(local_caminho)
    local["papel"] = "so_painel"
    local.setdefault("agentes", {}).setdefault(operador, "")
    base = _ler(pasta_projeto / "config.json")
    tem_dropbox = dropbox_existe(base)
    if not tem_dropbox:
        local.setdefault("dropbox_notas", {})["ativo"] = False
    _gravar(local_caminho, local)

    prefs_caminho = pasta_projeto / "estado" / "app.json"
    prefs = _ler(prefs_caminho)
    prefs["agente"] = operador
    _gravar(prefs_caminho, prefs)
    return {"operador": operador, "papel": "so_painel", "dropbox": tem_dropbox}


def main():
    try:
        r = preparar(sys.argv[1] if len(sys.argv) > 1 else "")
    except ValueError as e:
        print(f"   !!  {e}")
        return 1
    print(f"   OK  Papel: so_painel | Operador: {r['operador']}")
    print("   OK  Dropbox das notas encontrado" if r["dropbox"] else
          "   --  Dropbox das notas nao encontrado neste PC: a leitura das notas pelo Dropbox ficou desligada (o resto funciona)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
