"""Urgência: o hóspede diz que a NF está errada (valor, data, mês, nome, CPF/CNPJ, descrição) ou pede pra cancelar /
reemitir. O robô abre o PDF da NF (DANFSe do Dropbox), cruza com o que o cliente escreveu e monta um resumo curto
pro topo do e-mail (pedido do usuário, 08/10/2026): o que ele pede, o que a nota diz e se bate com a reclamação.
Só lê: nada é alterado no Dropbox nem no Outlook.
"""
import os
import re

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
    ("descrição", re.compile(r"descri[cç][aã]o|discrimina|rubrica|projeto|observa[cç]", re.I)),
    ("cancelar", re.compile(r"cancel|estorn|anula", re.I)),
    ("reemitir", re.compile(r"reemit|emitir (?:novamente|de novo|outra)|nova nota|nota nova|refaz|substitu|retific|corrig", re.I)),
]


def pedido_do_cliente(assunto, texto):
    """-> {"motivos": [...], "valores": ["480,00", ...], "datas": [...], "nfs": ["1254", ...]}"""
    t = f"{assunto or ''}\n{texto or ''}"
    return {"motivos": [m for m, p in _MOTIVOS if p.search(t)], "valores": list(dict.fromkeys(re.findall(_RS, t))),
            "datas": list(dict.fromkeys(re.findall(_DATA, t))), "nfs": list(dict.fromkeys(_NF.findall(t)))}


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
        "documento": _depois(linhas, r"tomador.*(?:cnpj|cpf)", r"(\d{2,3}\.\d{3}\.\d{3}[/-]\d{2,4}(?:-\d{2})?)"),
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


def resumo(pedido, nf, numero, assunto=""):
    """Frase curta pro topo: o que o cliente pede · o que a NF diz · se bate."""
    motivos = pedido["motivos"]
    pede = [m for m in motivos if m not in ("cancelar", "reemitir")]
    acao = "cancelar e refazer" if "cancelar" in motivos else "corrigir/reemitir"
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


def analisar(e, texto, itens_dropbox, notas_achadas=(), pdfs_anexos=()):
    """e: e-mail do espelho; pdfs_anexos: [(nome, texto)] dos PDFs anexados (a NF que o cliente mandou de volta).
    -> {"resumo", "nf": {...}|None, "arquivo", "pedido"}"""
    pedido = pedido_do_cliente(e.get("assunto", ""), texto)
    for nome, conteudo in pdfs_anexos:   # 1º: a própria NF anexada ao e-mail
        if re.search(r"nfs-?e", conteudo or "", re.I):
            nf = dados_do_pdf(conteudo)
            from controle_nf import ler_assunto_nf
            numero = nf.get("numero") or (ler_assunto_nf(os.path.splitext(nome)[0]) or ("",))[0]
            return {"resumo": resumo(pedido, nf, numero) + " (NF anexada ao e-mail)", "nf": nf,
                    "arquivo": nome, "pedido": pedido}
    # o nome do PDF anexado ("NF 6524 - CARLA LUIZA ... .pdf") diz o nº e o nome da nota mesmo quando o PDF é imagem
    from controle_nf import ler_assunto_nf
    pelo_anexo = [x for x in (ler_assunto_nf(os.path.splitext(nome)[0]) for nome, _ in pdfs_anexos) if x]
    numeros = [x[0] for x in pelo_anexo] + list(pedido["nfs"]) + [n.get("nf") for n in notas_achadas if n.get("nf")]
    nome_nf = pelo_anexo[0][1] if pelo_anexo else e.get("nome", "")
    item = achar_nf(numeros, nome_nf, e.get("hotel", ""), itens_dropbox) if numeros else None
    nf, numero = None, (numeros[0] if numeros else "")
    if item:
        numero = item[3][0]
        from arquivos import so_na_nuvem
        if os.path.exists(item[1]) and not so_na_nuvem(item[1]):   # só na nuvem: não baixa (regra do usuário)
            nf = dados_do_pdf(ler_pdf(item[1]))
    return {"resumo": resumo(pedido, nf, numero, e.get("assunto", "")), "nf": nf,
            "arquivo": item[0] if item else "", "pedido": pedido}
