"""NFs canceladas e substituídas = arquivos renomeados no Dropbox (só leitura):

    "NF 1212 - NOME"  ->  "(CANCELADA) NF 1212 - NOME"  ou  "(SUBSTITUIDA) NF 1212 - NOME"

- data: modificação do arquivo;
- hotel: prestador do PDF (cada hotel tem CNPJ próprio). A razão social com o nome do hotel decide
  sozinha; CNPJ de razão sem nome de hotel (ex.: "RF HOTEIS LTDA") vem de painel.cnpj_hoteis ou da
  votação com os pedidos da Central; PDF sem texto (escaneado) cai no pedido com o mesmo hóspede.
"""
import collections
import datetime
import json
import os
import re

from tratamento import normalizar

CANCELADA, SUBSTITUIDA = "cancelada", "substituida"
_PREFIXO = re.compile(r"^\s*\(([^)]*)\)\s*(.*)$")
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_RAZAO = re.compile(r"Nome Empresarial\s+(.+?)\s+(?:E-mail|Município|Endereço|Telefone)", re.I)
_PALAVRAS_COMUNS = {"de", "da", "do", "dos", "das", "e", "ltda", "me", "sa", "nf", "epp"}
VOTOS_MINIMOS, MAIORIA = 3, 0.75


def status_do_nome(nome):
    """'(CANCELADA) NF 1 - X' -> ('cancelada', 'NF 1 - X'); aceita os erros de digitação vistos nas
    pastas (SUBISTITUIDA, SUSBTITUIDA, CACELADA...). Sem prefixo de status -> (None, nome)."""
    m = _PREFIXO.match(nome or "")
    if not m:
        return None, nome
    p = normalizar(m.group(1)).replace(" ", "")
    if "ca" in p and "lad" in p:
        return CANCELADA, m.group(2)
    if re.search(r"su[bs]?[bis]*[st]*i?t?u", p):
        return SUBSTITUIDA, m.group(2)
    return None, nome


def ler_prestador(caminho):
    """-> (cnpj, razão social) do prestador na 1ª página do PDF; ('', '') se não der pra ler."""
    if not caminho.lower().endswith(".pdf"):
        return "", ""
    try:
        from pypdf import PdfReader
        texto = re.sub(r"\s+", " ", PdfReader(caminho).pages[0].extract_text() or "")
    except Exception:
        return "", ""
    i = texto.upper().find("PRESTADOR")
    bloco = texto[i:i + 400] if i >= 0 else texto[:400]
    cnpj, razao = _CNPJ.search(bloco), _RAZAO.search(bloco)
    return (cnpj.group(0) if cnpj else ""), (razao.group(1).strip() if razao else "")


def _palavras(texto):
    return " " + " ".join(re.findall(r"[a-z0-9]+", normalizar(texto))) + " "


def hotel_pela_razao(razao, nomes_hoteis, apelidos=None):
    """'REDE ANDRADE PAMPULHA HOTEL LTDA' -> 'PAMPULHA'; ambíguo ou sem nome de hotel -> None.
    Com dois candidatos, o mais específico ganha (ROYAL CRICIÚMA x CRICIÚMA)."""
    r = _palavras(razao)
    achou = {h for h in nomes_hoteis if _palavras(h) in r}
    achou |= {h for apelido, h in (apelidos or {}).items() if h in nomes_hoteis and _palavras(apelido) in r}
    achou = {h for h in achou if not any(h != o and _palavras(h) in _palavras(o) for o in achou)}
    return achou.pop() if len(achou) == 1 else None


def _tokens(nome):
    return [t for t in re.findall(r"[a-z]{2,}", normalizar(nome)) if t not in _PALAVRAS_COMUNS]


def _indice_de_pedidos(solicitacoes):
    """{1º nome: [(palavras do nome, data, hotel)]} — pra achar o pedido do hóspede de um arquivo."""
    indice = collections.defaultdict(list)
    for s in solicitacoes:
        try:
            dia = datetime.date.fromisoformat(s["data"])
        except (TypeError, ValueError):
            continue
        for nome in set(list(s.get("nomes", [])) + [s.get("nome", "")]):
            t = _tokens(nome)
            if t:
                indice[t[0]].append((set(t), dia, s["hotel"]))
    return indice


def _hotel_pelo_pedido(nome_hospede, dia, indice):
    """Pedido com o mesmo 1º nome + mais 1 palavra, feito até 15 dias depois ou 120 antes do arquivo."""
    t = _tokens(nome_hospede)
    if len(t) < 2:
        return None
    hoteis = {h for palavras, d, h in indice.get(t[0], []) if -15 <= (dia - d).days <= 120 and len(set(t) & palavras) >= 2}
    return hoteis.pop() if len(hoteis) == 1 else None


def varrer(pastas, cache):
    """Arquivos renomeados das pastas (com subpastas). cache {caminho: [mtime, cnpj, razão]} é atualizado
    no lugar: só PDF novo ou modificado é lido de novo."""
    achados, vistos = [], set()
    for pasta in pastas:
        for raiz, _, arquivos in os.walk(pasta):
            for nome in arquivos:
                tipo, resto = status_do_nome(nome)
                if not tipo or not nome.lower().endswith((".pdf", ".xml")):
                    continue
                caminho = os.path.join(raiz, nome)
                try:
                    mtime = os.path.getmtime(caminho)
                except OSError:
                    continue
                vistos.add(caminho)
                guardado = cache.get(caminho)
                if not guardado or guardado[0] != mtime:
                    cache[caminho] = guardado = [mtime, *ler_prestador(caminho)]
                m = re.search(r"(\d+)\s*-\s*([^-]+)", re.sub(r"\.(pdf|xml)$", "", resto, flags=re.I))
                achados.append({"caminho": caminho, "tipo": tipo, "data": datetime.date.fromtimestamp(mtime),
                                "nf": m.group(1) if m else "", "hospede": m.group(2).strip() if m else resto,
                                "cnpj": guardado[1], "razao": guardado[2]})
    for caminho in set(cache) - vistos:   # renomeado de volta / apagado
        del cache[caminho]
    return achados


def atribuir_hoteis(arquivos, nomes_hoteis, solicitacoes=(), apelidos=None, cnpj_hoteis=None):
    """Põe 'hotel' em cada arquivo (None = não identificado) e devolve {cnpj: hotel} usado."""
    indice = _indice_de_pedidos(solicitacoes)
    mapa = {c: h for c, h in (cnpj_hoteis or {}).items() if not str(c).startswith("_")}
    razoes = collections.defaultdict(set)
    for a in arquivos:
        a["pedido"] = _hotel_pelo_pedido(a["hospede"], a["data"], indice)
        if a["cnpj"] and a["razao"]:
            razoes[a["cnpj"]].add(a["razao"])
    for cnpj, rs in razoes.items():
        hoteis = {hotel_pela_razao(r, nomes_hoteis, apelidos) for r in rs} - {None}
        if cnpj not in mapa and len(hoteis) == 1:
            mapa[cnpj] = hoteis.pop()
    votos = collections.defaultdict(collections.Counter)
    for a in arquivos:
        if a["cnpj"] and a["cnpj"] not in mapa and a["pedido"]:
            votos[a["cnpj"]][a["pedido"]] += 1
    for cnpj, v in votos.items():
        hotel, n = v.most_common(1)[0]
        if n >= VOTOS_MINIMOS and n >= MAIORIA * sum(v.values()):
            mapa[cnpj] = hotel
    for a in arquivos:
        a["hotel"] = mapa.get(a["cnpj"]) if a["cnpj"] else a["pedido"]
    return mapa


def ler_cache(caminho):
    try:
        return json.load(open(caminho, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def salvar_cache(caminho, cache):
    temporario = f"{caminho}.tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(temporario, caminho)
