"""Trava do Claude Code contra comandos git que apagam trabalho (hook PreToolUse, skill git-guardrails).

Recebe no stdin o JSON da ferramenta (Bash ou PowerShell). Se o comando bater num padrão perigoso, sai com
código 2 e o Claude fica sem poder rodar. O push normal continua liberado: é assim que a entrega chega aos
4 PCs (main + Bernardo/Christian/clara). Bloqueia só o que some com trabalho: push forçado, apagar branch,
reset --hard, clean e checkout/restore de tudo.
"""
import json
import re
import sys

# "git" + opções globais (-C pasta, -c chave=valor) + o subcomando; o resto vai até o fim do comando (|, ;, &)
GIT = r"\bgit(?:\s+-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|\S+))*\s+"
RESTO = r"[^|;&]*"
PERIGOSOS = {
    "push forçado": GIT + r"push\b" + RESTO + r"(?:\s--force(?:-with-lease)?\b|\s-f\b|\s\+\S)",
    "apagar branch no GitHub": GIT + r"push\b" + RESTO + r"(?:\s--delete\b|\s-d\b|\s:\S)",
    "reset --hard": GIT + r"reset\b" + RESTO + r"\s--hard\b",
    "clean (apaga arquivos fora do git)": GIT + r"clean\b" + RESTO + r"\s-[a-zA-Z]*f",
    "apagar branch local": GIT + r"branch\b" + RESTO + r"\s(?:-D\b|--delete\s+--force\b)",
    "descartar todas as mudanças": GIT + r"(?:checkout|restore)(?:\s+--)?\s+\.(?:\s|$|[|;&])",
}


def motivo(comando):
    for nome, padrao in PERIGOSOS.items():
        if re.search(padrao, comando):
            return nome
    return None


def main():
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        comando = (json.load(sys.stdin).get("tool_input") or {}).get("command") or ""
    except ValueError:
        return 0
    achado = motivo(comando)
    if achado:
        print(f"BLOQUEADO ({achado}): o João não autorizou esse comando git. Peça a ele antes.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
