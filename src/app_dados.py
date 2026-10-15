"""Dados do app: monta a fila de solicitações a partir da Central e da aba Tratamento.

A aba Tratamento é um log só de inclusão (append-only). Cada ação de um agente vira uma linha e o
estado de cada solicitação é a dobra (fold) dessas linhas na ordem em que estão na planilha.
Como a ordem é decidida pelo servidor do Google, dois PCs clicando "Assumir" ao mesmo tempo
resolvem sem trava: vale a linha que entrou primeiro.
"""
import datetime
import re

from sheets import (VALORES_PENDENTE, _achar_coluna, _achar_colunas, _celula, _coluna_da_linha, _dados_para_conferencia,
                    _nome_titulo)
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


def dobrar_eventos(linhas, estados=None):
    """linhas da aba Tratamento (com cabeçalho) -> {chave: estado}. estados: continua de onde parou (só as
    linhas novas — o Painel não redobra 25 mil linhas a cada 15 s)."""
    estados = {} if estados is None else estados
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
    i_emails = _achar_colunas(cab, col.get("email_hospede", ""))
    if i_car is None:
        return []
    formato = detectar_formato_data((_celula(l, i_car) for l in linhas[1:]), cfg.get("formato_data_planilha", "americano"))
    saida = []
    for numero, linha in enumerate(linhas[1:], start=2):
        linha = list(linha) + [""] * (len(cab) - len(linha))
        carimbo = _celula(linha, i_car)
        if not carimbo:
            continue
        i_email = _coluna_da_linha(linha, i_emails)   # formulário antigo e novo na mesma aba (15/10/2026)
        esconder = {i_email} if i_email is not None else set()
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


_ENVIO_ROBO = re.compile(r"E-mail com a NF ([\d, ]+) enviado para (\S+) em (\d{2}/\d{2}/\d{4} \d{2}:\d{2})")
_ENVIO_PAINEL = re.compile(r'^"(.*?)" enviada ao h[oó]spede \((.*?)\) pela caixa')
_CONFIRMADA = re.compile(r"^NF (\d+) confirmada automaticamente: (.*)$")
ENVIO_PENDENTE_DIAS = 14   # = conferencia.dias_maximos: período em que o robô relê os e-mails enviados
_CONFERIDO_DOC = re.compile(r"^Conferido: CPF/CNPJ da NF (\d+) está certo")


def alertas_documento(est):
    """NF que saiu pra outro CPF/CNPJ (o robô abriu a nota e comparou com o formulário) -> (urgentes, avisos).
    urgentes: [{"nf", "texto"}] (alerta vermelho, vai pra Urgência) · avisos: o formulário é que veio digitado
    errado (a nota saiu com o documento válido). Some quando a NF é desfeita ou alguém marca "Está certo"."""
    ok = {m.group(1) for o in est["obs"] for m in [_CONFERIDO_DOC.match(o["texto"])] if m}
    urgentes, avisos = [], []
    for o in est["obs"]:
        m = _CONFIRMADA.match(o["texto"])
        if not m or m.group(1) not in est["nfs"] or m.group(1) in ok:
            continue
        for parte in m.group(2).split(" · "):
            if parte.startswith("⚠ CPF/CNPJ da NF"):
                urgentes.append({"nf": m.group(1), "texto": parte[2:]})
            elif parte.startswith("CPF/CNPJ do formulário"):
                avisos.append({"nf": m.group(1), "texto": parte})
    return urgentes, avisos


def _quando_br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]} {iso[11:16]}" if len(iso) >= 16 else iso


def envios_nf(sol, est):
    """E-mails com a NF que saíram pro hóspede -> [{nfs, para, quando}] (robô, Painel ou NF achada no e-mail)."""
    saida = []
    for o in est["obs"]:
        t = o["texto"]
        m = _ENVIO_ROBO.search(t)
        if m:
            saida.append({"nfs": [n.strip() for n in m.group(1).split(",") if n.strip()], "para": m.group(2),
                          "quando": m.group(3)})
            continue
        m = _ENVIO_PAINEL.match(t)
        if m:
            saida.append({"nfs": re.findall(r"\bNF\s*(\d+)", m.group(1), re.I), "para": m.group(2),
                          "quando": _quando_br(o["quando"])})
            continue
        m = _CONFIRMADA.match(t)
        if m and "e-mail" in m.group(2):
            saida.append({"nfs": [m.group(1)], "para": sol.get("email", ""), "quando": _quando_br(o["quando"])})
    return saida


def envio_pendente(nfs, envios, sol, hoje=None):
    """NF emitida e nenhum e-mail com ela pro hóspede. Só pra pedido dos últimos ENVIO_PENDENTE_DIAS: o robô relê
    os enviados desse período, e o e-mail da NF sai depois do pedido; mais antigo, sem registro não quer dizer
    que não foi (a conferência do ano marcou NFs antigas sem olhar o envio)."""
    if not nfs or envios:
        return False
    hoje = hoje or datetime.date.today()
    try:
        return (hoje - datetime.date.fromisoformat(sol.get("data") or "")).days <= ENVIO_PENDENTE_DIAS
    except ValueError:
        return False


def montar_fila(solicitacoes, estados, nfs_conferente=None, desde=None):
    """Junta solicitações + estados. nfs_conferente: {(aba, carimbo): [números]} do controle_nf local."""
    nfs_conferente = nfs_conferente or {}
    fila = []
    for s in solicitacoes:
        if desde and s["data"] and s["data"] < desde:
            continue
        est = estados.get(s["chave"], estado_inicial())
        conf = nfs_conferente.get((s["aba"], s["carimbo"]), [])
        envios = envios_nf(s, est)
        alertas = alertas_documento(est)
        todas_nfs = list(dict.fromkeys(est["nfs"] + list(conf)))
        fila.append({**s, "dono": est["dono"], "dono_desde": est["dono_desde"], "envios": envios,
                     "envio_pendente": envio_pendente(todas_nfs, envios, s),
                     "nfs": list(dict.fromkeys(est["nfs"] + list(conf))), "nfs_conferente": list(conf),
                     "tratativas": est["tratativas"], "obs": est["obs"],
                     "dividida": est["dividida"] if est["dividida"] is not None else s["partes"] > 1,
                     "partes": partes_esperadas(s, est),
                     "nota_unica": next((o["texto"] for o in est["obs"] if o["texto"].startswith("Hóspede aceita nota única:")), ""),
                     "historico": est["historico"], "situacao": situacao(s, est, conf),
                     "alerta_doc": alertas[0], "aviso_doc": alertas[1]})
    fila.sort(key=lambda x: (x["data"], x["carimbo"]), reverse=True)
    return fila


def _hora_do_formulario(texto):
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.datetime.strptime(str(texto).strip(), formato)
        except ValueError:
            pass
    return None


def ligar_caixa(solicitacoes, caixas):
    """Solicitações do robô na Caixa de Entrada dos PCs -> pedidos da planilha.
    caixas: {pc: espelho_emails.ler_pedidos(...)}. Liga pelo e-mail do hóspede + hora do formulário ("Enviado em").
    -> ({chave: {"pc", "caixa", "hotel", "recebido", "lido", "emails", "id"}}, [pedido mínimo dos que não achei])"""
    import hospedes
    por_email = {}
    for s in solicitacoes:
        for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
            por_email.setdefault(x, []).append(s)
    ligados, sem = {}, {}
    for pc, emails in caixas.items():
        for e in emails:
            for p in e.get("pedidos", []):
                hora = _hora_do_formulario(p.get("carimbo", ""))
                sem_segundos = len(str(p.get("carimbo", "")).strip()) <= 16   # "08/10/2026 19:01"
                candidatos = [s for s in por_email.get(p.get("email", ""), []) if hora and (inicio := hospedes.inicio_do_pedido(s))
                              and (inicio == hora or (sem_segundos and inicio.replace(second=0) == hora))]
                info = {"pc": pc, "caixa": e["caixa"], "hotel": e["hotel"], "recebido": e["recebido"], "lido": e["lido"],
                        "id": e["id"], "emails": 1}
                if candidatos:
                    k = candidatos[0]["chave"]
                    if k in ligados:   # o robô mandou o mesmo pedido mais de uma vez: fica 1, "não lido" se algum for
                        info = {**ligados[k], "emails": ligados[k]["emails"] + 1, "lido": ligados[k]["lido"] and e["lido"],
                                "recebido": max(ligados[k]["recebido"], e["recebido"])}
                    ligados[k] = info
                else:
                    chave = f"caixa:{pc}:{p.get('ref') or p.get('email')}:{p.get('carimbo')}"
                    sem[chave] = pedido_sem_formulario(chave, p, info)
    return ligados, list(sem.values())


def pedido_sem_formulario(chave, p, info):
    """Solicitação na Caixa de Entrada cujo formulário não achei na planilha: aparece igual (espelho), com aviso."""
    hora = _hora_do_formulario(p.get("carimbo", ""))
    return {"chave": chave, "aba": "", "hotel": info["hotel"].split(" / ")[0] if info["hotel"] else "", "linha": 0,
            "carimbo": p.get("carimbo", ""), "email": p.get("email", ""), "nome": p.get("nome", "") or "(sem nome)",
            "data": hora.date().isoformat() if hora else info["recebido"][:10], "enviado": True, "partes": 1,
            "emails": [p.get("email", "")], "nomes": [], "campos": [], "dono": "", "dono_desde": "", "envios": [],
            "envio_pendente": False, "nfs": [], "nfs_conferente": [], "tratativas": [], "obs": [], "dividida": False,
            "nota_unica": "", "historico": [], "situacao": NA_FILA, "alerta_doc": [], "aviso_doc": [], "hospede": chave,
            "repetido_de": "", "repetidos": [], "outros_pedidos": [], "outros_total": 0, "prazo": None,
            "na_caixa": info, "sem_formulario": True}


def juntar_fim(atuais, fim):
    """Leitura só do fim da Tratamento: atuais = o que eu já tinha; fim = o que veio de "A{len(atuais)}:H" (a
    última linha conhecida de novo, pra conferir). -> a aba inteira | None (mudou por baixo: reler inteira)."""
    if not atuais or not fim or [str(v) for v in fim[0]] != [str(v) for v in atuais[-1]]:
        return None
    return atuais + fim[1:] if len(fim) > 1 else atuais


def resolvida_em(item_fila):
    """Quando a solicitação foi resolvida (iso): a hora em que o e-mail com a NF saiu pro hóspede; sem envio
    registrado, o registro da NF. Não a hora da anotação — a conferência do robô anota envios antigos hoje."""
    envios = []
    for env in item_fila.get("envios", []):
        try:
            envios.append(datetime.datetime.strptime(env["quando"], "%d/%m/%Y %H:%M").isoformat())
        except (ValueError, KeyError):
            continue
    if envios:
        return max(envios)
    return max((h["quando"][:19] for h in item_fila.get("historico", []) if h["acao"] == NF), default="")


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
