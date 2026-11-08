"""Ajustes do Painel: tempos, limites, textos e assinaturas num arquivo de chave e valor (04/11/2026, pedido do João).

O arquivo `ajustes.json` fica ao lado do config.json, SÓ no PC do administrador (está no .gitignore: nunca sobe ao GitHub).
Quem não aparece no arquivo usa o valor de fábrica (src/sistema/ajustes_tabela.py, gerado; `ajustes.exemplo.json` mostra todos).
Valor inválido (fora do mínimo/máximo, tipo errado, chave com erro de digitação) NÃO derruba o Painel: usa o valor de fábrica
e anota o motivo em erros(), que vai para o log e para o aviso de saúde.

    from ajustes import valor
    LIMITE = valor("recarregar.limite_segundos")

Os valores são lidos quando o Painel liga: mudou o arquivo, reinicia o Painel.
"""
import copy
import json
import re
from pathlib import Path

from sistema.ajustes_tabela import ENTRADAS, GRUPOS

CAMINHO = Path(__file__).resolve().parent.parent / "ajustes.json"
_POR_CHAVE = {e[0]: e for e in ENTRADAS}
_COR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID_SELO = re.compile(r"^[a-z0-9]+$")
ESTADO = {"valores": None, "erros": []}


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _conferir(chave, padrao, minimo, maximo, tipo, v):
    """(valor_limpo, None) ou (None, motivo em português)."""
    if tipo == "cor":
        if not isinstance(v, str) or not _COR.match(v):
            return None, 'precisa ser uma cor no formato "#rrggbb"'
        return v.lower(), None
    if tipo == "textos":
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            return None, "precisa ser uma lista de textos entre aspas"
        return [x.strip() for x in v], None
    if tipo == "selos_nomes":
        if not isinstance(v, dict) or not all(_ID_SELO.match(str(k)) and (x is None or isinstance(x, str) and x.strip()) for k, x in v.items()):
            return None, 'precisa ser {"codigo": "Nome"} (código só com letras minúsculas e números)'
        return {k: x.strip() for k, x in {**padrao, **v}.items() if x is not None}, None
    if tipo == "selos_textos":
        if not isinstance(v, dict):
            return None, 'precisa ser {"codigo": {"nome": "...", "linhas": ["...", "..."]}}'
        for k, item in v.items():
            if item is None:
                continue
            if not _ID_SELO.match(str(k)):
                return None, f'o código "{k}" só pode ter letras minúsculas e números'
            if not (isinstance(item, dict) and isinstance(item.get("nome"), str) and item["nome"].strip()
                    and isinstance(item.get("linhas"), list) and 0 < len(item["linhas"]) <= 8
                    and all(isinstance(x, str) and x.strip() for x in item["linhas"])):
                return None, f'"{k}" precisa de "nome" e de 1 a 8 "linhas" de texto'
        return {k: x for k, x in {**copy.deepcopy(padrao), **v}.items() if x is not None}, None
    if tipo == "numeros":
        if not isinstance(v, dict) or not all(_numero(x) and x > 0 for x in v.values()):
            return None, "precisa ser {nome: número maior que zero}"
        return {**padrao, **{k: x for k, x in v.items()}}, None
    if isinstance(padrao, str):
        if not isinstance(v, str) or not v.strip():
            return None, "precisa ser um texto entre aspas"
        return v, None
    if not _numero(v):
        return None, "precisa ser um número (sem aspas)"
    if tipo == "decimal":   # tempo em segundos: aceita 4.5; fica inteiro quando não tem vírgula
        v = int(v) if float(v).is_integer() else float(v)
    elif isinstance(padrao, int) and not isinstance(padrao, bool):
        if isinstance(v, float) and not v.is_integer():
            return None, "precisa ser número inteiro"
        v = int(v)
    else:
        v = float(v)
    if minimo is not None and v < minimo or maximo is not None and v > maximo:
        return None, f"fica fora do aceito (de {minimo} a {maximo})"
    return v, None


def _ler_arquivo():
    try:
        with open(CAMINHO, encoding="utf-8") as f:
            bruto = json.load(f)
    except FileNotFoundError:
        return {}, []
    except json.JSONDecodeError as e:
        return {}, [f"ajustes.json com erro de digitação (linha {e.lineno}, coluna {e.colno}): {e.msg}. Usando os valores de fábrica."]
    except OSError as e:
        return {}, [f"Não consegui ler o ajustes.json ({e}). Usando os valores de fábrica."]
    if not isinstance(bruto, dict):
        return {}, ["ajustes.json precisa ser um objeto { ... }. Usando os valores de fábrica."]
    return bruto, []


def carregar(forcar=False):
    """Lê o arquivo uma vez (cache). Devolve {chave: valor} de TODAS as chaves da tabela."""
    if ESTADO["valores"] is not None and not forcar:
        return ESTADO["valores"]
    bruto, erros = _ler_arquivo()
    valores = {}
    achadas = set()
    for chave, padrao, minimo, maximo, _texto, tipo in ENTRADAS:
        grupo, _, nome = chave.partition(".")
        bloco = bruto.get(grupo)
        if isinstance(bloco, dict) and nome in bloco:
            achadas.add((grupo, nome))
            limpo, motivo = _conferir(chave, padrao, minimo, maximo, tipo, bloco[nome])
            if motivo:
                erros.append(f'ajustes.json: "{chave}" = {json.dumps(bloco[nome], ensure_ascii=False)[:80]} {motivo}. Usando {json.dumps(padrao, ensure_ascii=False)[:60]}.')
                limpo = None
            valores[chave] = copy.deepcopy(padrao) if limpo is None else limpo
        else:
            valores[chave] = copy.deepcopy(padrao)
    for grupo, bloco in bruto.items():   # chave que não existe = erro de digitação: avisa em vez de ignorar calado
        if grupo.startswith("_"):
            continue
        if grupo not in GRUPOS or not isinstance(bloco, dict):
            erros.append(f'ajustes.json: o grupo "{grupo}" não existe (veja ajustes.exemplo.json).')
            continue
        for nome in bloco:
            if not nome.startswith("_") and (grupo, nome) not in achadas:
                erros.append(f'ajustes.json: a chave "{grupo}.{nome}" não existe (erro de digitação? veja ajustes.exemplo.json).')
    alta, media = valores.get("filtro.prioridade_alta_a_partir_de"), valores.get("filtro.prioridade_media_a_partir_de")
    if alta is not None and media is not None and media >= alta:
        erros.append(f'ajustes.json: "filtro.prioridade_media_a_partir_de" ({media}) precisa ser menor que "filtro.prioridade_alta_a_partir_de" ({alta}). Usando os dois valores de fábrica.')
        for k in ("filtro.prioridade_alta_a_partir_de", "filtro.prioridade_media_a_partir_de"):
            valores[k] = copy.deepcopy(_POR_CHAVE[k][1])
    ESTADO["valores"], ESTADO["erros"] = valores, erros
    return valores


def valor(chave):
    """Valor ajustado (ou o de fábrica). Chave que não está na tabela é erro de quem programa: KeyError."""
    if chave not in _POR_CHAVE:
        raise KeyError(f"ajuste desconhecido: {chave}")
    return copy.deepcopy(carregar()[chave])


def erros():
    carregar()
    return list(ESTADO["erros"])


def para_tela():
    """Só os grupos que a tela usa, aninhados {grupo: {nome: valor}}. Nada de segredo aqui: são tempos e limites."""
    saida = {}
    for chave, valor_ in carregar().items():
        grupo, _, nome = chave.partition(".")
        if grupo in GRUPOS_DA_TELA:
            saida.setdefault(grupo, {})[nome] = valor_
    return saida


GRUPOS_DA_TELA = ("tela", "filtro", "recarregar")


def js_da_tela():
    """O que a rota /ajustes.js entrega: window.AJUSTES e aj("grupo.nome"), lidos pelas peças da tela (que têm o valor de fábrica como reserva)."""
    return ("window.AJUSTES = " + json.dumps(para_tela(), ensure_ascii=False) + ";\n"
            "window.aj = chave => chave.split('.').reduce((o, p) => (o == null ? undefined : o[p]), window.AJUSTES);\n")


def diferencas():
    """[(chave, valor de fábrica, valor em uso)] só do que o ajustes.json mudou de fato."""
    atual = carregar()
    return [(e[0], e[1], atual[e[0]]) for e in ENTRADAS if atual[e[0]] != e[1]]


if __name__ == "__main__":   # python src\ajustes.py  -> confere o ajustes.json e diz o que está errado
    import sys

    from sistema.console_utf8 import garantir_utf8
    garantir_utf8()
    problemas = erros()
    if not CAMINHO.exists():
        print("Não há ajustes.json: o Painel usa todos os valores de fábrica. Para mudar algo, copie ajustes.exemplo.json para ajustes.json.")
    for p in problemas:
        print("⚠", p)
    if CAMINHO.exists() and not problemas:
        print("✅ ajustes.json OK")
    if CAMINHO.exists():
        mudou = diferencas()
        print(f"Você mudou {len(mudou)} ajuste(s) em relação ao valor de fábrica." if mudou else "Todos os valores estão iguais aos de fábrica.")
        for chave, fabrica, usado in mudou:
            if isinstance(fabrica, dict) and isinstance(usado, dict):   # assinaturas, prazos: mostra só quais itens mexeram
                print(f"  {chave}: mudou {', '.join(sorted(k for k in set(fabrica) | set(usado) if fabrica.get(k) != usado.get(k)))}")
            else:
                print(f"  {chave}: fábrica {json.dumps(fabrica, ensure_ascii=False)[:50]}  ->  em uso {json.dumps(usado, ensure_ascii=False)[:50]}")
    sys.exit(1 if problemas else 0)
