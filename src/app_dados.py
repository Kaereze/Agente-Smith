"""Dados do app: monta a fila de solicitações a partir da Central e da aba Tratamento.

A aba Tratamento é um log só de inclusão (append-only). Cada ação de um agente vira uma linha e o
estado de cada solicitação é a dobra (fold) dessas linhas na ordem em que estão na planilha.
Como a ordem é decidida pelo servidor do Google, dois PCs clicando "Assumir" ao mesmo tempo
resolvem sem trava: vale a linha que entrou primeiro.
"""
import datetime

from sheets import VALORES_PENDENTE, _achar_coluna, _celula, _dados_para_conferencia, _nome_titulo
from tratamento import campos_para_email, detectar_formato_data, ler_data, normalizar

ABA_TRATAMENTO = "Tratamento"
CABECALHO_TRATAMENTO = ["Quando", "Agente", "PC", "Aba", "Carimbo", "E-mail", "Ação", "Valor"]

ASSUMIR, LIBERAR, NF, DESFAZER_NF, TRATATIVA, OBS, DIVIDIDA = (
    "ASSUMIR", "LIBERAR", "NF", "DESFAZER_NF", "TRATATIVA", "OBS", "DIVIDIDA")
ACOES = {ASSUMIR, LIBERAR, NF, DESFAZER_NF, TRATATIVA, OBS, DIVIDIDA}

AGUARDANDO_ENVIO, NA_FILA, EM_TRATAMENTO, EM_TRATATIVA, NF_PARCIAL, CONCLUIDA = (
    "aguardando_envio", "na_fila", "em_tratamento", "tratativa", "nf_parcial", "concluida")


def chave(aba, carimbo, email):
    return f"{aba} | {carimbo} | {(email or '').strip().lower()}"


def evento(agora, agente, pc, aba, carimbo, email, acao, valor=""):
    if acao not in ACOES:
        raise ValueError(f"ação desconhecida: {acao}")
    return [agora.isoformat(timespec="seconds"), agente, pc, aba, carimbo, (email or "").strip().lower(), acao, str(valor)]


def estado_inicial():
    return {"dono": "", "dono_desde": "", "nfs": [], "tratativas": [], "obs": [], "dividida": None,
            "historico": []}


def dobrar_eventos(linhas):
    """linhas da aba Tratamento (com cabeçalho) -> {chave: estado}"""
    estados = {}
    for l in linhas[1:]:
        l = list(l) + [""] * (len(CABECALHO_TRATAMENTO) - len(l))
        quando, agente, pc, aba, carimbo, email, acao, valor = (str(v).strip() for v in l[:8])
        if acao not in ACOES or not aba:
            continue
        e = estados.setdefault(chave(aba, carimbo, email), estado_inicial())
        e["historico"].append({"quando": quando, "agente": agente, "acao": acao, "valor": valor})
        if acao == ASSUMIR:
            if not e["dono"]:
                e["dono"], e["dono_desde"] = agente, quando
        elif acao == LIBERAR:
            if e["dono"] == agente or valor == "forcar":
                e["dono"], e["dono_desde"] = "", ""
        elif acao == NF:
            if valor and valor not in e["nfs"]:
                e["nfs"].append(valor)
        elif acao == DESFAZER_NF:
            e["nfs"] = [n for n in e["nfs"] if n != valor]
        elif acao == TRATATIVA:
            e["tratativas"].append({"quando": quando, "agente": agente, "texto": valor})
        elif acao == OBS:
            e["obs"].append({"quando": quando, "agente": agente, "texto": valor})
        elif acao == DIVIDIDA:
            e["dividida"] = normalizar(valor) in ("sim", "true", "1")
    return estados


def ler_solicitacoes(aba, hotel, linhas, cfg):
    """Todas as linhas de uma aba de hotel da Central, enviadas ou não."""
    if not linhas:
        return []
    cab = [str(c).strip() for c in linhas[0]]
    col = cfg["colunas"]
    i_env, i_car = _achar_coluna(cab, col["enviado"]), _achar_coluna(cab, col["carimbo"])
    i_email = _achar_coluna(cab, col.get("email_hospede", ""))
    if i_car is None:
        return []
    formato = detectar_formato_data((_celula(l, i_car) for l in linhas[1:]), cfg.get("formato_data_planilha", "americano"))
    esconder = {i_email} if i_email is not None else set()
    saida = []
    for numero, linha in enumerate(linhas[1:], start=2):
        linha = list(linha) + [""] * (len(cab) - len(linha))
        carimbo = _celula(linha, i_car)
        if not carimbo:
            continue
        email = _celula(linha, i_email)
        emails, nomes, partes = _dados_para_conferencia(cab, linha, cfg)
        data = ler_data(carimbo, formato)
        saida.append({
            "chave": chave(aba, carimbo, email), "aba": aba, "hotel": hotel, "linha": numero,
            "carimbo": carimbo, "email": email.lower(), "nome": _nome_titulo(cab, linha, cfg),
            "data": data.isoformat() if data else "",
            "enviado": i_env is not None and normalizar(_celula(linha, i_env)) not in VALORES_PENDENTE,
            "partes": partes, "emails": emails, "nomes": nomes,
            "campos": campos_para_email(cab, linha, cfg.get("colunas_ocultas", []), formato,
                                        cfg.get("colunas_documento", {}), esconder),
        })
    return saida


def partes_esperadas(sol, est):
    """Quantas NFs fecham o pedido: "Não é dividida" (ou o hóspede pediu nota única) = 1, mesmo
    que o formulário diga dividida; "Nota dividida" sem número = 2."""
    if est.get("dividida") is False:
        return 1
    return max(int(sol.get("partes") or 1), 2 if est.get("dividida") else 1)


def situacao(sol, est, nfs_conferente=()):
    nfs = list(dict.fromkeys(list(est["nfs"]) + list(nfs_conferente)))
    partes = partes_esperadas(sol, est)
    if nfs and len(nfs) >= partes:
        return CONCLUIDA
    if nfs:
        return NF_PARCIAL
    if est["dono"]:
        return EM_TRATAMENTO
    if est["tratativas"]:
        return EM_TRATATIVA
    return NA_FILA if sol["enviado"] else AGUARDANDO_ENVIO


def montar_fila(solicitacoes, estados, nfs_conferente=None, desde=None):
    """Junta solicitações + estados. nfs_conferente: {(aba, carimbo): [números]} do controle_nf local."""
    nfs_conferente = nfs_conferente or {}
    fila = []
    for s in solicitacoes:
        if desde and s["data"] and s["data"] < desde:
            continue
        est = estados.get(s["chave"], estado_inicial())
        conf = nfs_conferente.get((s["aba"], s["carimbo"]), [])
        fila.append({**s, "dono": est["dono"], "dono_desde": est["dono_desde"],
                     "nfs": list(dict.fromkeys(est["nfs"] + list(conf))), "nfs_conferente": list(conf),
                     "tratativas": est["tratativas"], "obs": est["obs"],
                     "dividida": est["dividida"] if est["dividida"] is not None else s["partes"] > 1,
                     "partes": partes_esperadas(s, est),
                     "nota_unica": next((o["texto"] for o in est["obs"] if o["texto"].startswith("Hóspede aceita nota única:")), ""),
                     "historico": est["historico"], "situacao": situacao(s, est, conf)})
    fila.sort(key=lambda x: (x["data"], x["carimbo"]), reverse=True)
    return fila


def nfs_do_controle(registro_dict):
    """estado/controle_nf.json do conferente -> {(aba, carimbo): [números de NF]}"""
    saida = {}
    for s in (registro_dict or {}).get("solicitacoes", {}).values():
        nfs = [n for n, d in s.get("nfs", {}).items() if not d.get("conferir")]
        if nfs and s.get("aba") and s.get("carimbo"):
            saida.setdefault((s["aba"], s["carimbo"]), [])
            saida[(s["aba"], s["carimbo"])] += [n for n in nfs if n not in saida[(s["aba"], s["carimbo"])]]
    return saida


def quem_ganhou(estados, chave_sol):
    return estados.get(chave_sol, estado_inicial())["dono"]


def agora():
    return datetime.datetime.now().astimezone()
