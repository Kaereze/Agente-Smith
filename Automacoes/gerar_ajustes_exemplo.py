"""Gera o ajustes.exemplo.json e cuida do ajustes.json deste PC (04/11/2026, pedido do João).

    .venv\\Scripts\\python.exe Automacoes\\gerar_ajustes_exemplo.py          -> reescreve ajustes.exemplo.json (todos os ajustes, valor de fábrica e explicação)
    .venv\\Scripts\\python.exe Automacoes\\gerar_ajustes_exemplo.py --meu    -> cria o ajustes.json se não houver; se houver, só acrescenta as chaves novas

O ajustes.json fica só neste PC (está no .gitignore). Os seus valores nunca são trocados por esta ferramenta.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from ajustes_tabela import ENTRADAS, GRUPOS  # noqa: E402

LEIA_ME = ("Ajustes do Painel Fiscal. Para mudar algo, altere só o NÚMERO ou o TEXTO depois dos dois pontos e salve. "
           "As linhas que começam com _ajuda são só explicação: o Painel as ignora. "
           "Depois de salvar, feche e abra o Painel de novo (menu do operador, 'Fechar o Painel'). "
           "Número vai sem aspas; texto vai entre aspas. Valor fora do aceito ou chave com erro de digitação não derruba o Painel: "
           "ele usa o valor de fábrica e mostra um aviso na faixa de saúde. Este arquivo fica só no PC do administrador e nunca vai ao GitHub.")


def faixa(padrao, minimo, maximo, tipo):
    if tipo in (None, "decimal") and isinstance(padrao, (int, float)) and not isinstance(padrao, bool):
        return f" (aceita de {minimo} a {maximo}{', pode ter casa decimal com PONTO, como 4.5' if tipo == 'decimal' else ''}; de fábrica {padrao})"
    return ""


def montar(valores=None):
    """{grupo: {...}} com tudo; valores = {chave: valor} que o usuário já tem (mantidos)."""
    valores = valores or {}
    saida = {"_LEIA_ME": LEIA_ME}
    for grupo, texto in GRUPOS.items():
        bloco = {"_ajuda": texto}
        for chave, padrao, minimo, maximo, explicacao, tipo in ENTRADAS:
            g, _, nome = chave.partition(".")
            if g != grupo:
                continue
            bloco["_ajuda_" + nome] = explicacao + faixa(padrao, minimo, maximo, tipo)
            bloco[nome] = valores.get(chave, padrao)
        saida[grupo] = bloco
    return saida


def valores_do_arquivo(caminho):
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    achados, extras = {}, {}
    for grupo, bloco in bruto.items():
        if not isinstance(bloco, dict):
            continue
        for nome, v in bloco.items():
            if not nome.startswith("_"):
                achados[f"{grupo}.{nome}"] = v
    conhecidas = {e[0] for e in ENTRADAS}
    for chave, v in achados.items():
        if chave not in conhecidas:
            extras[chave] = v
    return achados, extras


def escrever(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv):
    from console_utf8 import garantir_utf8
    garantir_utf8()
    if "--meu" in argv:
        caminho = RAIZ / "ajustes.json"
        existente = caminho.exists()
        achados, extras = valores_do_arquivo(caminho) if existente else ({}, {})
        dados = montar(achados)
        for chave, v in extras.items():   # chave desconhecida do usuário: mantém (o Painel avisa), nunca apaga
            g, _, nome = chave.partition(".")
            dados.setdefault(g, {})[nome] = v
        escrever(caminho, dados)
        novas = len([e for e in ENTRADAS if e[0] not in achados]) if existente else len(ENTRADAS)
        print(f"ajustes.json {'atualizado' if existente else 'criado'}: {len(ENTRADAS)} ajustes ({novas} {'novos' if existente else 'com o valor de fábrica'}).")
        return 0
    escrever(RAIZ / "ajustes.exemplo.json", montar())
    print(f"ajustes.exemplo.json gravado com {len(ENTRADAS)} ajustes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
