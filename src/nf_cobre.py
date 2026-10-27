"""A NF já enviada cobre o que o hóspede pede agora? (27/10/2026, desenho aprovado pelo João).

O robô NUNCA tira nem apaga e-mail da entrada sozinho: o hóspede às vezes pede outra coisa depois de receber a nota (primeiro
só diárias, depois consumo). Aqui só se compara, no conjunto, o que o e-mail novo pede (datas, serviço, CPF/CNPJ e a descrição,
quando o corpo pede uma específica) com o que a nota enviada traz. O que não bate vira "pede nova nota" (Urgência). Mover a
conversa para a pasta "NF enviada" é sempre um clique da pessoa.
"""
import re

from controle_nf import _DATA, documento_tomador, ler_descricao_nota, servicos_no_texto
from tratamento import normalizar

NOMES = {"diaria": "diárias", "consumo": "consumo", "estacionamento": "estacionamento"}
# só vira "pede nova nota" se o e-mail realmente pede algo: "obrigado pela nota" nunca dispara
_INTENCAO = re.compile(r"\b(nova|novo|outra|outro|segunda|mais uma|emitir|emitam|emita|emissao|preciso|precisamos|gostaria|gostariamos|"
                       r"poderiam|poderia|solicito|solicitamos|solicitar|favor|necessito|necessitamos|corrig\w*|refaz\w*|alterar|incluir|"
                       r"separad\w*|acrescent\w*|esqueceram|faltou)\b")
_DATA_EMAIL = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/\d{2,4})?(?![\d/])")
_DOC = re.compile(r"(?<![\d.])(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})(?!\d)")
_DESCRICAO = re.compile(r"descri[cç][aã]o[^\"“\n]{0,40}[\"“]([^\"”\n]{6,160})[\"”]|"
                        r"\bconforme\s+((?:contrato|proposta|pedido|empenho|projeto|evento|pronac)[^.\n]{3,120})", re.I)


def _dm(d, m):
    return f"{int(d):02d}/{int(m):02d}"


def pede_do_texto(texto):
    """O que o texto do e-mail pede. -> {"intencao", "servicos", "datas", "docs", "descricao"}"""
    t = texto or ""
    desc = _DESCRICAO.search(t)
    return {"intencao": bool(_INTENCAO.search(normalizar(t))), "servicos": servicos_no_texto(t),
            "datas": {_dm(d, m) for d, m in _DATA_EMAIL.findall(t) if 1 <= int(d) <= 31 and 1 <= int(m) <= 12},
            "docs": {re.sub(r"\D", "", x) for x in _DOC.findall(t)},
            "descricao": ((desc.group(1) or desc.group(2)).strip() if desc else "")}


def cobertura_da_nota(texto):
    """O que uma nota enviada cobre. -> {"servicos", "datas", "doc", "texto", "legivel"}"""
    t = texto or ""
    desc = ler_descricao_nota(t)
    servicos = set(desc["servicos"]) if desc and desc["servicos"] else servicos_no_texto(t)
    datas = {x for x in ([desc["checkin"], desc["checkout"]] if desc else []) if x}
    datas |= {_dm(d, m) for d, m, _a in _DATA.findall(t)}
    return {"servicos": servicos, "datas": datas, "doc": documento_tomador(t), "texto": normalizar(t), "legivel": len(t.strip()) >= 60}


def _lista(itens):
    return ", ".join(sorted(NOMES.get(i, i) for i in itens))


def analisar(texto_email, textos_das_notas):
    """texto_email: só a mensagem nova (sem a citada). textos_das_notas: textos dos PDFs das NF já enviadas deste pedido.
    -> {"cobre": True | False | None (sem nota legível), "pede_nova": bool, "motivos": [...],
        "linhas": [{"ok": True | False, "rotulo", "texto"}]}"""
    notas = [cobertura_da_nota(t) for t in textos_das_notas]
    notas = [n for n in notas if n["legivel"]]
    if not notas:
        return {"cobre": None, "pede_nova": False, "motivos": [],
                "linhas": [{"ok": None, "rotulo": "Nota", "texto": "não consegui ler a NF enviada: confira"}]}
    cobre_serv = set().union(*(n["servicos"] for n in notas))
    cobre_datas = set().union(*(n["datas"] for n in notas))
    docs = {n["doc"] for n in notas if n["doc"]}
    texto_notas = " ".join(n["texto"] for n in notas)
    p = pede_do_texto(texto_email)
    linhas, motivos = [], []

    def linha(ok, rotulo, texto):
        linhas.append({"ok": ok, "rotulo": rotulo, "texto": texto})
        if ok is False:
            motivos.append(f"{rotulo.lower()}: {texto}")

    if cobre_datas:
        fora = sorted(p["datas"] - cobre_datas)
        if p["intencao"] and fora:
            linha(False, "Datas", f"pede {', '.join(fora)} · a nota não tem essas datas")
        else:
            linha(True, "Datas", "a nota cobre a estadia do pedido")
    if cobre_serv:
        faltam = p["servicos"] - cobre_serv
        if p["intencao"] and faltam:
            linha(False, "Serviço", f"pede {_lista(faltam)} · a nota só tem {_lista(cobre_serv)}")
        else:
            linha(True, "Serviço", f"{_lista(cobre_serv)} · a nota cobre")
    if docs:
        outros = sorted(p["docs"] - docs)
        if p["intencao"] and outros:
            linha(False, "CPF/CNPJ", f"pede {outros[0]} · a nota tem {sorted(docs)[0]}")
        else:
            linha(True, "CPF/CNPJ", "o documento da nota confere")
    if p["descricao"]:
        if normalizar(p["descricao"]) in texto_notas:
            linha(True, "Descrição", "a descrição pedida está na nota")
        else:
            linha(False, "Descrição", f"pede “{p['descricao']}” · a nota não traz")
    pede_nova = any(l["ok"] is False for l in linhas)
    return {"cobre": not pede_nova, "pede_nova": pede_nova, "motivos": motivos, "linhas": linhas}


def motivo_curto(analise, nfs):
    """Texto da Urgência: "Pede nova nota: consumo não está na NF 2186"."""
    if not analise.get("pede_nova"):
        return ""
    return f"Pede nova nota (NF {', '.join(str(n) for n in nfs)}): {analise['motivos'][0]}"
