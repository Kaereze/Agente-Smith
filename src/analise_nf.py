"""Urgência: o hóspede diz que a NF está errada (valor, data, mês, nome, CPF/CNPJ, descrição) ou pede pra cancelar /
reemitir. O robô abre o PDF da NF (DANFSe do Dropbox), cruza com o que o cliente escreveu e monta um resumo curto
pro topo do e-mail (pedido do usuário, 08/10/2026): o que ele pede, o que a nota diz e se bate com a reclamação.
Só lê: nada é alterado no Dropbox nem no Outlook.
"""
import json
import os
import re

from controle_nf import documento_tomador, formatar_documento
from log_util import configurar_logging
from tratamento import normalizar

logger = configurar_logging("analise_nf")

_RS = r"R\$\s*([\d.]{1,12},\d{2})"
_DATA = r"(\d{2}/\d{2}/\d{4})"
_NF = re.compile(r"\b(?:NF|NFS-?e|nota(?:\s+fiscal)?)\s*(?:n[º°o.]*\s*)?(\d{2,7})\b", re.I)
_MOTIVOS = [   # (motivo, padrão no texto do cliente)
    ("valor", re.compile(r"valor|R\$|pre[cç]o|cobrad|a mais|a menos", re.I)),
    ("data", re.compile(r"\bdata\b|check.?in|check.?out|entrada|sa[ií]da|di[aá]rias?\b|per[ií]odo", re.I)),
    ("mês", re.compile(r"\bm[eê]s\b|compet[eê]ncia|janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro", re.I)),
    ("nome", re.compile(r"\bnome\b|raz[aã]o social|tomador", re.I)),
    ("CPF/CNPJ", re.compile(r"\bcpf\b|\bcnpj\b|documento", re.I)),
    ("descrição", re.compile(r"descri[cç][aã]o|discrimina|rubrica|projeto|observa[cç]|pronac|empenho|contrato|"
                             r"ordem de compra|centro de custo|n[uú]mero do pedido", re.I)),
    ("cancelar", re.compile(r"cancel|estorn|anula", re.I)),
    ("reemitir", re.compile(r"reemit|emitir (?:novamente|de novo|outra)|nova nota|nota nova|refaz|substitu|retific|corrig", re.I)),
]


_DOC = re.compile(r"(?<![\d.])(\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")
VERSAO = 3   # muda quando a regra da análise muda: o espelho refaz as análises antigas na próxima volta (3: texto na nota)
ROTULOS = {"valor": "valor da nota", "data": "datas da hospedagem", "mês": "mês / competência",
           "nome": "nome do tomador", "CPF/CNPJ": "CPF/CNPJ do tomador", "descrição": "descrição da nota"}


_FIM_DO_TEXTO = re.compile(r"\n--\s*\n|aviso de confidencialidade|confidentiality notice|enviado do meu", re.I)
_RECLAMA = re.compile(r"falt|inclu|corrig|corre[cç][aã]o|errad|incorret|equivocad|alter|constar|\bconsta\b|deveria|precis|"
                      r"mudar|troc|ajust|diverg|n[aã]o\s+(?:saiu|veio|est[aá]|tem|consta|bate|confere)", re.I)
_ELOGIA = re.compile(r"\bcorret[oa]s?\b|\bcert[oa]s?\b|n[aã]o\s+precisa|est[aá]\s+ok\b", re.I)


# Texto que o hóspede quer na nota, entre aspas (usuário, 20/10/2026: "a própria hóspede disse na mensagem": "não consta a
# identificação “UEM / Fulana”"). Só vale aspas num trecho que fala de constar/incluir/identificação na nota.
_ASPAS = re.compile(r"[“\"«‘]\s*([^“”\"«»‘’\n]{2,120}?)\s*[”\"»’]")
_PEDE_TEXTO = re.compile(r"identifica|\bconsta|inclu|inser|coloc|acrescent|adicion|falt|aparec|mencion|escrit|descri|"
                         r"observa|discrimina|refer[eê]ncia|conter|contenha", re.I)


def textos_pedidos(texto):
    """Os textos entre aspas que o cliente pede pra constar na nota -> ["UEM / Fulana", ...] (até 3)."""
    limpo = _FIM_DO_TEXTO.split(texto or "")[0]
    achados = []
    for trecho in re.split(r"(?<=[.!?;])\s+|\n", limpo):
        if not _PEDE_TEXTO.search(trecho):
            continue
        for m in _ASPAS.finditer(trecho):
            pedido = m.group(1).strip(" .,;:")
            if len(re.sub(r"\W", "", pedido)) >= 2 and pedido not in achados:
                achados.append(pedido)
    return achados[:3]


def _so_letras(texto):
    return re.sub(r"[^a-z0-9]+", " ", normalizar(texto)).strip()


def onde_aparece(pedido, texto_nf):
    """O texto pedido está na NF? Sem acento, maiúscula ou pontuação ("UEM / Fulana" = "UEM - FULANA").
    -> "inteiro" | "em partes" (todas as palavras, mas não juntas) | "" (não aparece)"""
    alvo, nf = _so_letras(pedido), f" {_so_letras(texto_nf)} "
    if not alvo:
        return ""
    if f" {alvo} " in nf:
        return "inteiro"
    palavras = [w for w in alvo.split() if len(w) > 1]
    return "em partes" if palavras and all(f" {w} " in nf for w in palavras) else ""


def pontos_de_reclamacao(texto):
    """Quantas vezes cada assunto aparece num trecho de reclamação ("faltou incluir a descrição", "valor incorreto").
    Trecho que elogia ("o valor está correto") não conta; assinatura e aviso de confidencialidade ficam de fora.
    Caso Natália (09/10/2026): o 1º assunto citado era o valor ("estava com o valor correto"), mas o pedido era a
    descrição (rubrica, projeto, Pronac)."""
    limpo = _FIM_DO_TEXTO.split(texto or "")[0]
    pontos = {}
    for trecho in re.split(r"[.!?;\n,]|\bno entanto\b|\bpor[ée]m\b|\bmas\b", limpo, flags=re.I):
        if not _RECLAMA.search(trecho) or _ELOGIA.search(trecho):
            continue
        for m, p in _MOTIVOS:
            if m in ROTULOS and p.search(trecho):
                pontos[m] = pontos.get(m, 0) + 1
    return pontos


def pedido_do_cliente(assunto, texto):
    """-> {"motivos": [...], "valores": ["480,00", ...], "datas": [...], "nfs": ["1254", ...], "documentos": [dígitos],
    "posicoes": {motivo: onde aparece primeiro}, "termos": {motivo: [palavras achadas]}}"""
    texto = _FIM_DO_TEXTO.split(texto or "")[0]
    t = f"{texto}\n{assunto or ''}"   # o corpo primeiro: o assunto costuma ser genérico ("Nota fiscal")
    posicoes, termos = {}, {}
    for m, p in _MOTIVOS:
        achados = list(p.finditer(t))
        if achados:
            posicoes[m] = achados[0].start()
            termos[m] = list(dict.fromkeys(a.group(0).strip().lower() for a in achados))[:4]
    textos = textos_pedidos(texto)
    return {"motivos": (["texto"] if textos else []) + [m for m, _ in _MOTIVOS if m in posicoes], "textos": textos,
            "valores": list(dict.fromkeys(re.findall(_RS, t))),
            "datas": list(dict.fromkeys(re.findall(_DATA, t))), "nfs": list(dict.fromkeys(_NF.findall(t))),
            "documentos": list(dict.fromkeys(re.sub(r"\D", "", d) for d in _DOC.findall(texto or ""))),
            "posicoes": posicoes, "termos": termos, "pontos": pontos_de_reclamacao(texto)}


def motivo_principal(pedido):
    """O que o cliente quer corrigir, em destaque (usuário, 09/10/2026): o assunto que mais aparece nos trechos de
    reclamação; empate (ou nenhum trecho claro) = o 1º que ele cita. -> (motivo, detalhe, outros motivos)"""
    pontos, posicoes = pedido.get("pontos", {}), pedido.get("posicoes", {})
    if pedido.get("textos"):   # o cliente disse exatamente o que tem de constar: é isso, com as palavras dele
        outros = [ROTULOS[m] for m in pedido.get("motivos", []) if m in ROTULOS and pontos.get(m)]
        return "incluir na nota: " + ", ".join(f"“{x}”" for x in pedido["textos"]), "", outros
    citados = sorted((-pontos.get(m, 0), p, m) for m, p in posicoes.items() if m in ROTULOS)
    if pontos:   # com trecho de reclamação, os outros são só os que também foram reclamados
        citados = [c for c in citados if c[0] < 0]
    citados = [(p, m) for _, p, m in citados]
    if not citados:
        if "cancelar" in pedido["motivos"]:
            return "cancelar a nota", "", []
        return "refazer a nota (o cliente não disse o que mudar)", "", []
    principal = citados[0][1]
    detalhe = {"valor": ", ".join(f"R$ {v}" for v in pedido["valores"][:2]),
               "data": ", ".join(pedido["datas"][:2]), "mês": ", ".join(pedido["datas"][:2]),
               "CPF/CNPJ": ", ".join(formatar_documento(d) for d in pedido.get("documentos", [])[:2])}.get(principal, "")
    if principal == "descrição":
        detalhe = ", ".join(x for x in pedido["termos"].get("descrição", []) if not x.startswith(("descri", "observa")))
    outros = [ROTULOS[m] for _, m in citados[1:]]
    return ROTULOS[principal], detalhe, outros


def _depois(linhas, rotulo, padrao, alcance=3):
    """Valor que vem logo depois do rótulo (o DANFSe põe o rótulo numa linha e o valor na seguinte)."""
    for i, l in enumerate(linhas):
        if re.search(rotulo, l, re.I):
            for prox in [l] + linhas[i + 1:i + 1 + alcance]:
                m = re.search(padrao, prox)
                if m:
                    return m.group(1)
    return ""


def dados_do_pdf(texto):
    """Texto do DANFSe -> {"numero", "valor", "emissao", "competencia", "checkin", "checkout", "diarias", "documento"}"""
    linhas = [l.strip() for l in (texto or "").splitlines() if l.strip()]
    return {
        "numero": _depois(linhas, r"n[uú]mero da nfs", r"^(\d{1,7})$", 2) or _depois(linhas, r"^n[uú]mero\b", r"^(\d{1,7})\b", 2),
        "valor": _depois(linhas, r"valor l[ií]quido da nfs", _RS) or _depois(linhas, r"valor (?:total da nfs|do servi[cç]o|total)", _RS),
        "emissao": _depois(linhas, r"emiss[aã]o da nfs", _DATA) or _depois(linhas, r"emiss[aã]o", _DATA),
        "competencia": _depois(linhas, r"compet[eê]ncia", r"(\d{2}/\d{2}/\d{4}|\d{2}/\d{4})"),
        "checkin": _depois(linhas, r"check.?in", _DATA, 0),
        "checkout": _depois(linhas, r"check.?out", _DATA, 0),
        "diarias": _depois(linhas, r"quantidade de di[aá]ria", r"(\d+)", 0),
        "documento": documento_tomador(texto),
    }


def ler_pdf(caminho):
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages[:3])
    except Exception as e:
        logger.debug(f"PDF ilegível ({caminho}): {e}")
        return ""


def achar_nf(numeros, nome, hotel, itens):
    """itens = envio_nf.listar_notas_dropbox -> (nome, caminho, mtime, (nº, nome na NF)). O nº da NF só é único dentro
    de um hotel: com vários do mesmo número, vale o do nome do hóspede (ou o do hotel na pasta)."""
    palavras = {p for p in normalizar(nome or "").split() if len(p) > 2}
    candidatos = [it for it in itens if it[3][0] in numeros and it[0].lower().endswith(".pdf")]
    if len(candidatos) > 1 and palavras:
        por_nome = [it for it in candidatos if palavras & set(normalizar(it[3][1]).split())]
        candidatos = por_nome or candidatos
    if len(candidatos) > 1 and hotel:
        por_hotel = [it for it in candidatos if normalizar(hotel.split(" / ")[0]) in normalizar(it[1])]
        candidatos = por_hotel or candidatos
    return max(candidatos, key=lambda it: it[2]) if candidatos else None


def _num(v):
    try:
        return float(v.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def na_nf(nf, numero):
    """Ex.: Na NF 6524: R$ 366,00 · competência 09/2026 · hospedagem 01/09 a 03/09 · CPF 123.456.789-00"""
    if not nf:
        return f"NF{(' ' + numero) if numero else ''} não achada no Dropbox — conferir à mão"
    partes = [f"Na NF{(' ' + numero) if numero else ''}: {('R$ ' + nf['valor']) if nf.get('valor') else 'valor ?'}"]
    if nf.get("competencia"):
        partes.append(f"competência {nf['competencia']}")
    if nf.get("checkin") and nf.get("checkout"):
        partes.append(f"hospedagem {nf['checkin']} a {nf['checkout']}")
    if nf.get("documento"):
        partes.append(("CNPJ " if len(nf["documento"]) == 14 else "CPF ") + formatar_documento(nf["documento"]))
    return " · ".join(partes)


def comparar(pedido, nf, texto_nf=""):
    """O que o cliente escreveu x o que a NF diz -> [frases]. Diferença de CPF/CNPJ começa com ⚠. texto_nf: o PDF
    inteiro, pra procurar o texto que o cliente pediu em qualquer parte da nota (discriminação, observação, tomador)."""
    if not nf:
        return []
    saida = []
    for pedido_txt in pedido.get("textos", []):
        onde = onde_aparece(pedido_txt, texto_nf) if texto_nf.strip() else None
        saida.append(f"conferir à mão se “{pedido_txt}” está na nota (o PDF não tem texto legível)" if onde is None
                     else f"“{pedido_txt}” não aparece em nenhuma parte da nota" if not onde
                     else f"“{pedido_txt}” já aparece na nota" + (" (as palavras estão lá, mas não juntas)" if onde == "em partes" else ""))
    motivos = pedido["motivos"]
    if "valor" in motivos and pedido["valores"] and nf.get("valor"):
        citados = [v for v in pedido["valores"] if _num(v) is not None]
        if any(abs(_num(v) - _num(nf["valor"])) < 0.01 for v in citados):
            outros = [v for v in citados if abs(_num(v) - _num(nf["valor"])) >= 0.01]
            saida.append(f"cliente cita o valor da nota e pede R$ {outros[0]}" if outros else "o valor citado é o da nota")
        elif citados:
            saida.append(f"cliente fala em R$ {citados[0]} — diferente da nota")
    if ("data" in motivos or "mês" in motivos) and pedido["datas"] and nf.get("checkin"):
        fora = [d for d in pedido["datas"] if d not in (nf.get("checkin"), nf.get("checkout"), nf.get("competencia"))]
        if fora:
            saida.append(f"cliente cita {', '.join(fora[:2])} — não está na nota")
    docs = [d for d in pedido.get("documentos", []) if len(d) in (11, 14)]
    if docs and nf.get("documento"):
        if nf["documento"] in docs:
            saida.append("o CPF/CNPJ que o cliente escreveu é o da nota")
        else:
            saida.append(f"⚠ cliente escreveu {formatar_documento(docs[0])}; a nota saiu com "
                         f"{formatar_documento(nf['documento'])}")
    return saida


def resumo(pedido, nf, numero, assunto=""):
    """Frase curta pro topo: o que o cliente pede · o que a NF diz · se bate."""
    motivos = pedido["motivos"]
    pede = [m for m in motivos if m not in ("cancelar", "reemitir")]
    acao = "cancelar e refazer" if "cancelar" in motivos else "corrigir/reemitir"
    pede = ["texto na nota: " + ", ".join(f"“{x}”" for x in pedido.get("textos", [])) if m == "texto" else m for m in pede]
    partes = [f"Pede para {acao} a NF{(' ' + numero) if numero else ''}" + (f" ({', '.join(pede)})" if pede else "")]
    if not nf:
        partes.append("NF não achada no Dropbox — conferir à mão")
        return " · ".join(partes)
    partes.append(f"na NF: {('R$ ' + nf['valor']) if nf.get('valor') else 'valor ?'}"
                  + (f", competência {nf['competencia']}" if nf.get("competencia") else "")
                  + (f", hospedagem {nf['checkin']} a {nf['checkout']}" if nf.get("checkin") and nf.get("checkout") else ""))
    if "valor" in motivos and pedido["valores"] and nf.get("valor"):
        citados = [v for v in pedido["valores"] if _num(v) is not None]
        if any(abs(_num(v) - _num(nf["valor"])) < 0.01 for v in citados):
            outros = [v for v in citados if abs(_num(v) - _num(nf["valor"])) >= 0.01]
            partes.append(f"cliente cita o valor da nota e pede R$ {outros[0]}" if outros else "o valor citado é o da nota")
        else:
            partes.append(f"cliente fala em R$ {citados[0]} — diferente da nota")
    if ("data" in motivos or "mês" in motivos) and pedido["datas"] and nf.get("checkin"):
        fora = [d for d in pedido["datas"] if d not in (nf.get("checkin"), nf.get("checkout"), nf.get("competencia"))]
        if fora:
            partes.append(f"cliente cita {', '.join(fora[:2])} — não está na nota")
    return " · ".join(partes)


def completo(pedido, nf, numero, arquivo, origem="", texto_nf=""):
    """Tudo que a tela mostra: motivo em destaque, o que a NF diz, a comparação e os outros assuntos citados."""
    motivo, detalhe, outros = motivo_principal(pedido)
    comparacao = comparar(pedido, nf, texto_nf)
    if pedido.get("textos") and nf:   # o motivo já diz se o texto pedido está ou não na NF
        falta = any("não aparece" in c for c in comparacao)
        detalhe = f"não aparece na NF{(' ' + numero) if numero else ''}" if falta else \
            f"já aparece na NF{(' ' + numero) if numero else ''}" if any("já aparece" in c for c in comparacao) else detalhe
    return {"resumo": resumo(pedido, nf, numero) + origem, "nf": nf, "arquivo": arquivo, "pedido": pedido,
            "motivo": motivo, "detalhe": detalhe, "outros": outros, "na_nf": na_nf(nf, numero) + origem,
            "comparacao": comparacao}


def compacto(analise):
    """Pra célula "Análise" da aba Correio_<PC> (JSON curto)."""
    return json.dumps({"v": VERSAO, "r": analise["resumo"], "m": analise["motivo"], "d": analise["detalhe"], "o": analise["outros"],
                       "nf": analise["na_nf"], "c": analise["comparacao"]}, ensure_ascii=False, separators=(",", ":"))


def ler_compacto(celula):
    """Célula "Análise" -> (resumo, {m, d, o, nf, c} | None). PC com a versão antiga grava só o resumo (texto)."""
    celula = str(celula or "").strip()
    if celula.startswith("{"):
        try:
            d = json.loads(celula)
            return str(d.get("r", "")), d
        except ValueError:
            pass
    return celula, None


def analisar(e, texto, itens_dropbox, notas_achadas=(), pdfs_anexos=()):
    """e: e-mail do espelho; pdfs_anexos: [(nome, texto)] dos PDFs anexados (a NF que o cliente mandou de volta).
    -> {"resumo", "nf": {...}|None, "arquivo", "pedido", "motivo", "detalhe", "outros", "na_nf", "comparacao"}"""
    pedido = pedido_do_cliente(e.get("assunto", ""), texto)
    for nome, conteudo in pdfs_anexos:   # 1º: a própria NF anexada ao e-mail
        if re.search(r"nfs-?e", conteudo or "", re.I):
            nf = dados_do_pdf(conteudo)
            from controle_nf import ler_assunto_nf
            numero = nf.get("numero") or (ler_assunto_nf(os.path.splitext(nome)[0]) or ("",))[0]
            return completo(pedido, nf, numero, nome, " (NF anexada ao e-mail)", conteudo)
    # o nome do PDF anexado ("NF 6524 - CARLA LUIZA ... .pdf") diz o nº e o nome da nota mesmo quando o PDF é imagem
    from controle_nf import ler_assunto_nf
    pelo_anexo = [x for x in (ler_assunto_nf(os.path.splitext(nome)[0]) for nome, _ in pdfs_anexos) if x]
    numeros = [x[0] for x in pelo_anexo] + list(pedido["nfs"]) + [n.get("nf") for n in notas_achadas if n.get("nf")]
    nome_nf = pelo_anexo[0][1] if pelo_anexo else e.get("nome", "")
    item = achar_nf(numeros, nome_nf, e.get("hotel", ""), itens_dropbox) if numeros else None
    nf, numero, texto_nf = None, (numeros[0] if numeros else ""), ""
    if item:
        numero = item[3][0]
        from arquivos import so_na_nuvem
        if os.path.exists(item[1]) and not so_na_nuvem(item[1]):   # só na nuvem: não baixa (regra do usuário)
            texto_nf = ler_pdf(item[1])
            nf = dados_do_pdf(texto_nf)
    return completo(pedido, nf, numero, item[0] if item else "", texto_nf=texto_nf)
