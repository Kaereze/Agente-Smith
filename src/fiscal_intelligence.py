"""Leitura (somente) da planilha Fiscal Intelligence, gravada pelo Mail Analytics.

Abas usadas:
  Agente_<operador>   uma linha por dia × hotel: e-mails, ligações, cancelamentos, NFs
  Log_Eventos         FIM_DE_SEMANA_GUARDADO / FIM_DE_SEMANA_SOMADO (sex/sáb entram somados no domingo)
  Status_Execucao     status da última execução de cada operador
  Status_Operadores   última execução bem-sucedida
  Painel_Controle     E2 = sinal de vida do escutar_comando; B3 = status; C2 = último consolidado enviado

Branco nas colunas numéricas conta como 0, igual ao relatório do próprio Mail Analytics.
"""
import datetime
import re

from tratamento import normalizar

ABA_POR_OPERADOR = {"Agente_Joao": "João", "Agente_Clara": "Clara", "Agente_Cristian": "Cristian",
                    "Agente_Bernardo": "Bernardo"}
ABAS_FIXAS = ["Log_Eventos", "Status_Execucao", "Status_Operadores", "Painel_Controle"]
METRICAS = ("recebidos", "enviados", "ligacoes", "cancelamentos", "nfs")
_COLUNAS = {"data": ["data"], "hotel": ["hotel"], "recebidos": ["emails recebidos"], "enviados": ["emails enviados"],
            "ligacoes": ["ligacoes"], "cancelamentos": ["substituicoes/cancelamentos"], "nfs": ["nfs emitidas"]}
FRESCOR_SINAL_SEGUNDOS = 40


def _data(texto):
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", str(texto or ""))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _int(texto):
    digitos = re.sub(r"\D", "", str(texto or ""))
    return int(digitos) if digitos else 0


def _indices(cabecalho):
    cab = [normalizar(c) for c in cabecalho]
    padrao = {"data": 0, "hotel": 1, "recebidos": 2, "enviados": 3, "ligacoes": 4, "cancelamentos": 5, "nfs": 6}
    return {k: next((cab.index(n) for n in nomes if n in cab), padrao[k]) for k, nomes in _COLUNAS.items()}


def ler_metricas(linhas, operador, cadastro, desde):
    """-> (registros, avisos). Registro: data, hotel (canônico), hotel_original, operador + METRICAS.
    Mesmo dia × hotel repetido: vale a última linha (e vira aviso)."""
    if not linhas:
        return [], []
    idx = _indices(linhas[0])
    por_chave, repetidos, sem_cadastro = {}, set(), set()
    for l in linhas[1:]:
        cel = lambda k: l[idx[k]] if len(l) > idx[k] else ""
        dia = _data(cel("data"))
        original = str(cel("hotel")).strip()
        if not dia or not original or dia < desde:
            continue
        hotel = cadastro.canonico(original)
        if hotel is None:
            sem_cadastro.add(original)
            hotel = original
        chave = (dia, hotel)
        if chave in por_chave:
            repetidos.add(chave)
        por_chave[chave] = {"data": dia, "hotel": hotel, "hotel_original": original, "operador": operador,
                            **{m: _int(cel(m)) for m in METRICAS}}
    avisos = [f"{operador}: {d:%d/%m} {h} aparece repetido — usando a última linha" for d, h in sorted(repetidos)]
    avisos += [f"{operador}: hotel '{h}' não está no Cadastro_Hoteis" for h in sorted(sem_cadastro)]
    return list(por_chave.values()), avisos


def fins_de_semana(linhas_log):
    """-> (somados {(operador, domingo): texto}, guardados {(operador, dia): domingo})"""
    somados, guardados = {}, {}
    for l in linhas_log[1:]:
        if len(l) < 4:
            continue
        operador, evento, detalhe = str(l[1]).strip(), str(l[2]).strip(), str(l[3]).strip()
        if evento == "FIM_DE_SEMANA_SOMADO":
            m = re.match(r"^(\d{2}/\d{2}/\d{4}):\s*(.+?)\s+somados", detalhe)
            if m and _data(m.group(1)):
                texto = m.group(2) if re.search(r"\d{2}/\d{2}", m.group(2)) else "fim de semana somado"
                somados[(operador, _data(m.group(1)))] = texto
        elif evento == "FIM_DE_SEMANA_GUARDADO":
            datas = re.findall(r"\d{2}/\d{2}/\d{4}", detalhe)
            if len(datas) >= 2:
                guardados[(operador, _data(datas[0]))] = _data(datas[-1])
    return somados, guardados


def _tabela(linhas):
    if not linhas:
        return []
    cab = [str(c).strip() for c in linhas[0]]
    return [{cab[i]: (str(l[i]).strip() if i < len(l) else "") for i in range(len(cab))} for l in linhas[1:] if l]


def _datahora(texto):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.datetime.strptime(str(texto).strip()[:19], fmt)
        except ValueError:
            continue
    return None


def filtrar_avisos(detalhe, ignorar_hoteis=(), desde=None, datas_conhecidas=()):
    """Tira do Detalhe do Mail Analytics os avisos de hotéis ignorados e os que só citam datas
    anteriores a `desde` ou dias sem dado já conhecidos. -> (avisos que ficam, avisos ignorados)"""
    ignorados = {normalizar(h) for h in ignorar_hoteis}
    conhecidas = set(datas_conhecidas)
    ficam, saem = [], []
    for parte in (p.strip() for p in re.split(r";\s*", detalhe or "")):
        if not parte:
            continue
        m = re.search(r"conectaram hoje:\s*([^—]+)", parte)
        hoteis_citados = [normalizar(h) for h in m.group(1).split(",")] if m else []
        datas = [_data(d) for d in re.findall(r"\d{2}/\d{2}/\d{4}", parte)]
        so_ignorados = bool(hoteis_citados) and all(h.strip() in ignorados for h in hoteis_citados)
        so_antigo = bool(datas) and all(d and ((desde and d < desde) or d in conhecidas) for d in datas)
        (saem if so_ignorados or so_antigo else ficam).append(parte)
    return ficam, saem


def lacunas_por_operador(config_lacunas):
    """{"*": ["06/09/2026"], "Cristian": [...]} -> {operador: {date}}; "*" vale pra todos."""
    todos = {_data(d) for d in config_lacunas.get("*", [])} - {None}
    return {op: todos | ({_data(d) for d in config_lacunas.get(op, [])} - {None}) for op in ABA_POR_OPERADOR.values()}


def saude(abas, metricas, guardados, hoje, lido_em, ignorar_hoteis=(), desde=None, lacunas=None):
    """Situação de cada operador (como o "Verificar as 4 Máquinas") + o escutar_comando."""
    ontem = hoje - datetime.timedelta(days=1)
    status = {r.get("Operador"): r for r in _tabela(abas.get("Status_Execucao", []))}
    ultimas = {r.get("Operador"): r.get("Última Execução Bem-Sucedida", "") for r in _tabela(abas.get("Status_Operadores", []))}
    com_dado = {(m["operador"], m["data"]) for m in metricas}
    operadores = []
    for operador in ABA_POR_OPERADOR.values():
        if (operador, ontem) in com_dado:
            situacao = "puxado"
        elif (operador, ontem) in guardados:
            situacao = "guardado"
        else:
            situacao = "nao_puxado"
        st = status.get(operador, {})
        avisos, ignorados = filtrar_avisos(st.get("Detalhe", ""), ignorar_hoteis, desde, (lacunas or {}).get(operador, ()))
        estado = st.get("Status", "")
        if estado == "ATENCAO" and not avisos and ignorados:
            estado = "OK"   # só avisos de hotel ignorado / de antes do período do painel
        operadores.append({"operador": operador, "ontem": situacao, "domingo": str(guardados.get((operador, ontem), "")),
                           "status": estado, "detalhe": "; ".join(avisos), "avisos_ignorados": len(ignorados),
                           "ultima_execucao": ultimas.get(operador, "")})

    painel = abas.get("Painel_Controle", [])
    cel = lambda linha, col: str(painel[linha][col]).strip() if len(painel) > linha and len(painel[linha]) > col else ""
    sinal_bruto = cel(1, 4)
    desatualizado = "|DESATUALIZADO" in sinal_bruto
    sinal = _datahora(sinal_bruto.replace("|DESATUALIZADO", ""))
    # O sinal é regravado a cada ~8s, mas só relemos a aba de tempos em tempos: compara com o momento da leitura
    online = bool(sinal and lido_em and sinal >= lido_em - datetime.timedelta(seconds=FRESCOR_SINAL_SEGUNDOS))
    escuta = {"online": online, "desatualizado": desatualizado, "sinal": sinal.isoformat() if sinal else "",
              "comando": cel(1, 1), "status": cel(2, 1), "ultimo_consolidado": cel(1, 2)}
    return {"operadores": operadores, "escutar_comando": escuta, "ontem": ontem.isoformat()}


def ler(backend, planilha_id, cadastro, desde, hoje=None, agora=None, ignorar_hoteis=(), lacunas_conhecidas=None):
    """Lê tudo numa chamada só. -> dict com metricas, fins de semana, saúde e avisos.
    Hotéis em ignorar_hoteis ficam fora das métricas e dos avisos."""
    hoje = hoje or datetime.date.today()
    agora = agora or datetime.datetime.now()
    abas, erros = backend.ler_abas(planilha_id, list(ABA_POR_OPERADOR) + ABAS_FIXAS)
    metricas, avisos = [], []
    for aba, operador in ABA_POR_OPERADOR.items():
        regs, av = ler_metricas(abas.get(aba, []), operador, cadastro, desde)
        metricas += regs
        avisos += av
    ignorados = {normalizar(h) for h in ignorar_hoteis}
    metricas = [m for m in metricas if normalizar(m["hotel"]) not in ignorados]
    avisos = [a for a in avisos if not any(normalizar(h) in normalizar(a) for h in ignorar_hoteis)]
    somados, guardados = fins_de_semana(abas.get("Log_Eventos", []))
    lacunas = lacunas_por_operador(lacunas_conhecidas or {})
    for op, dias in lacunas.items():   # nota no gráfico: o dia está baixo porque não tem dado, não por queda
        for dia in dias:
            somados.setdefault((op, dia), "sem dado (conhecido)")
    avisos += [f"Não consegui ler a aba '{a}' do Fiscal Intelligence" for a in erros]
    return {"metricas": metricas, "fins_de_semana": somados, "guardados": guardados,
            "saude": saude(abas, metricas, guardados, hoje, agora, ignorar_hoteis, desde, lacunas),
            "avisos": avisos, "lido_em": agora}
