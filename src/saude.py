"""Saúde do sistema — uma faixa vermelha no topo do Painel quando algo sai do normal (usuário, 11/10/2026).

Motivo: a cópia das planilhas dos hotéis ficou 2,5 dias parada (08/10 21:36 a 11/10) e ninguém viu; e a Caixa de
Saída do Outlook já travou com 5 e-mails sem ninguém perceber. Cada PC publica na coluna "Saúde" da aba PCs_Painel
quantos e-mails estão presos na Caixa de Saída dele e (o PC principal) quando foi a última cópia que deu certo.
"""
import datetime

COPIA_ATRASADA_MIN = 35          # a cópia roda a cada 10 min (15/10/2026): duas voltas perdidas + folga
SAIDA_TRAVADA_MIN = 10           # e-mail parado na Caixa de Saída há mais que isso
HORARIO_COPIA = ("07:00", "23:30")
SEM_EMAIL_HORAS = 6              # caixa deste PC sem e-mail novo há mais que isso...
OUTRO_RECEBEU_HORAS = 2          # ...enquanto outro PC recebeu há menos que isso = Outlook não está baixando
HORARIO_EMAIL = ("08:00", "22:00")


def coluna(saida_travada, ultima_copia="", sem_cadastro=(), robo="", recebido=""):
    """-> texto da coluna "Saúde" deste PC: "saida=2;copia=2026-10-11T13:14:38;cad=CAMPO GRANDE|IDEAL;robo=iso;rec=iso"."""
    partes = [f"saida={int(saida_travada or 0)}"]
    if ultima_copia:
        partes.append(f"copia={ultima_copia}")
    if sem_cadastro:
        partes.append("cad=" + "|".join(str(x).replace(";", ",").replace("=", "-") for x in sem_cadastro))
    if robo:
        partes.append(f"robo={robo}")
    if recebido:
        partes.append(f"rec={recebido}")
    return ";".join(partes)


def ultimo_recebido(ns):
    """Hora (iso) do e-mail mais novo nas Caixas de Entrada deste Outlook (13/10/2026: o Outlook do Cristian ficou 3 dias
    sem baixar e-mail e ninguém viu). Só lê; não abre item nem muda lido."""
    mais_novo = None
    vistos = set()
    for conta in ns.Accounts:
        try:
            pasta = conta.DeliveryStore.GetDefaultFolder(6)
            if pasta.EntryID in vistos:
                continue
            vistos.add(pasta.EntryID)
            itens = pasta.Items
            itens.Sort("[ReceivedTime]", True)
            item = itens.GetFirst()
            if item is None:
                continue
            q = item.ReceivedTime
            quando = datetime.datetime(q.year, q.month, q.day, q.hour, q.minute, q.second)
            mais_novo = max(mais_novo, quando) if mais_novo else quando
        except Exception:
            continue
    return mais_novo.isoformat(timespec="seconds") if mais_novo else ""


def ler_coluna(texto):
    saida = {}
    for parte in str(texto or "").split(";"):
        k, _, v = parte.partition("=")
        if k.strip():
            saida[k.strip()] = v.strip()
    try:
        saida["saida"] = int(saida.get("saida") or 0)
    except ValueError:
        saida["saida"] = 0
    saida["cad"] = [x for x in str(saida.get("cad", "")).split("|") if x]
    return saida


def nome_da_caixa(caixa):
    """notafiscal@redeandradecampogrande.com.br -> "CAMPOGRANDE" (sugestão; dá pra corrigir antes de cadastrar)."""
    import re
    dominio = caixa.split("@", 1)[-1].split(".")[0]
    return (re.sub(r"^(redeandrade|hotel)", "", dominio) or dominio).upper()


def cadastro_faltando(pcs, emails_cadastrados, planilhas_sem_cadastro):
    """Caixas de hotel (notafiscal@) que estão no Outlook de algum PC e planilhas de hotel na pasta que não estão no
    Cadastro_Hoteis. -> [{"hotel", "email", "agente", "motivo"}] com sugestão de linha (planilha + caixa juntas)."""
    import re
    from tratamento import normalizar
    cadastrados = {e.lower() for e in emails_cadastrados if e}
    caixas = []
    for p in pcs:
        for c in p.get("contas_lista", []):
            if c.startswith("notafiscal@") and c not in cadastrados and c not in [x["email"] for x in caixas]:
                caixas.append({"email": c, "agente": p.get("agente", ""), "hotel": nome_da_caixa(c)})
    saida = []
    for nome in planilhas_sem_cadastro:
        m = re.search(r"\(([^()]+)\)\s*\(respostas\)", nome)
        hotel = (m.group(1) if m else nome).strip().upper()
        chave = normalizar(hotel).replace(" ", "")
        par = next((c for c in caixas if normalizar(c["hotel"]).replace(" ", "") == chave), None)
        if par:
            caixas.remove(par)
        saida.append({"hotel": hotel, "email": par["email"] if par else "", "agente": par["agente"] if par else "",
                      "motivo": "planilha de formulário sem hotel no cadastro" + (" · caixa no Outlook do PC de " + par["agente"] if par else "")})
    saida += [{**c, "motivo": f"caixa no Outlook do PC de {c['agente']} sem hotel no cadastro"} for c in caixas]
    return saida


def _data(texto):
    try:
        return datetime.datetime.fromisoformat(str(texto)[:19])
    except ValueError:
        return None


def problemas(pcs, agora=None):
    """pcs: rede_pcs.ler_pcs (com "saude" lida). -> [{"nivel": "erro"|"aviso", "texto", "pc"}], o mais grave primeiro."""
    agora = agora or datetime.datetime.now()
    saida = []
    versoes = {}
    for p in pcs:
        if p.get("online") and p.get("versao"):
            versoes[p["versao"]] = versoes.get(p["versao"], 0) + 1
    versao_da_maioria = max(versoes, key=lambda v: (versoes[v], v)) if versoes else ""
    copias = [c for c in (_data(p.get("saude", {}).get("copia")) for p in pcs) if c]
    if copias:
        ultima = max(copias)
        no_horario = HORARIO_COPIA[0] <= agora.strftime("%H:%M") <= HORARIO_COPIA[1]
        if no_horario and agora - ultima > datetime.timedelta(minutes=COPIA_ATRASADA_MIN):
            saida.append({"nivel": "erro", "pc": "", "texto": f"A cópia dos hotéis não roda desde {ultima:%d/%m %H:%M}: "
                          "formulários novos não estão entrando na Central"})
    for p in pcs:
        if not p.get("online"):
            continue
        quem = p.get("agente") or p.get("pc")
        n = p.get("saude", {}).get("saida", 0)
        if n:
            saida.append({"nivel": "erro", "pc": p["pc"], "texto": f"Caixa de Saída do Outlook de {quem} travada: "
                          f"{n} e-mail(s) parado(s) há mais de {SAIDA_TRAVADA_MIN} min"})
        if p.get("outlook") == "fechado":
            saida.append({"nivel": "erro", "pc": p["pc"], "texto": f"Outlook fechado no PC de {quem}: o robô não lê as caixas dele"})
        elif p.get("outlook") == "sem janela":
            saida.append({"nivel": "erro", "pc": p["pc"], "texto": f"Outlook do PC de {quem} aberto sem janela: não baixa e-mail "
                          "(o guardião está abrindo; se continuar, abra o Outlook pelo ícone e aperte F9)"})
        elif p.get("conferencia_atrasada"):
            saida.append({"nivel": "aviso", "pc": p["pc"], "texto": f"Robô do PC de {quem} parado (sem conferir o Outlook há mais de 10 min)"})
        if versao_da_maioria and p.get("versao") and p["versao"] != versao_da_maioria and len(versoes) > 1:
            saida.append({"nivel": "aviso", "pc": p["pc"], "texto": f"PC de {quem} rodando outra versão ({p['versao']}): "
                          "use \"Atualizar todos os PCs\" em Máquinas"})
    recebidos = {p["pc"]: _data(p.get("saude", {}).get("rec")) for p in pcs if p.get("online")}
    recebidos = {pc: r for pc, r in recebidos.items() if r}
    if len(recebidos) > 1 and HORARIO_EMAIL[0] <= agora.strftime("%H:%M") <= HORARIO_EMAIL[1]:
        for p in pcs:
            r = recebidos.get(p.get("pc"))
            outros = [x for pc, x in recebidos.items() if pc != p.get("pc")]
            if r and outros and agora - r > datetime.timedelta(hours=SEM_EMAIL_HORAS) \
                    and agora - max(outros) < datetime.timedelta(hours=OUTRO_RECEBEU_HORAS):
                saida.append({"nivel": "erro", "pc": p["pc"], "texto": f"Nenhum e-mail novo chega ao Outlook de "
                              f"{p.get('agente') or p['pc']} desde {r:%d/%m %H:%M}: confira o Enviar/Receber (F9) nesse PC"})
    robos = [r for r in (_data(p.get("saude", {}).get("robo")) for p in pcs) if r]
    if robos and HORARIO_COPIA[0] <= agora.strftime("%H:%M") <= HORARIO_COPIA[1] and \
            agora - max(robos) > datetime.timedelta(minutes=COPIA_ATRASADA_MIN):
        saida.append({"nivel": "erro", "pc": "", "texto": f"O robô de envio não roda desde {max(robos):%d/%m %H:%M}: "
                      "solicitações novas não estão indo para os hotéis"})
    import re
    faltam = sorted({(re.search(r"\(([^()]+)\)\s*\(respostas\)", x) or [None, x])[1] for p in pcs for x in p.get("saude", {}).get("cad", [])})
    if faltam:
        saida.append({"nivel": "aviso", "pc": "", "texto": f"Cadastro incompleto: {', '.join(faltam[:4])}{'…' if len(faltam) > 4 else ''} sem cadastro — "
                      "as planilhas desses hotéis não são copiadas (veja em Máquinas)"})
    return sorted(saida, key=lambda x: x["nivel"] != "erro")


PEDIDO_SEM_ENVIO_HORAS = 2       # ciclo de 10 min + até 75 min esperando o robô antigo: passou disso, está parado


def pedidos_sem_envio(solicitacoes, agora=None, horas=PEDIDO_SEM_ENVIO_HORAS):
    """Pedido de formulário que está na Central sem TRUE há mais de `horas` (usuário, 15/10/2026: "faça com que esse
    erro nunca mais aconteça"). O ciclo copia+envia roda a cada 10 min; o que passa de 2 h ficou para trás.
    -> [aviso] (no horário do robô), agrupado por hotel."""
    import re
    agora = agora or datetime.datetime.now()
    if not HORARIO_COPIA[0] <= agora.strftime("%H:%M") <= HORARIO_COPIA[1]:
        return []
    por_hotel = {}
    for s in solicitacoes or []:
        if s.get("enviado") or not s.get("data"):
            continue
        m = re.search(r"(\d{1,2}):(\d{2})", str(s.get("carimbo", "")))
        try:
            chegou = datetime.datetime.fromisoformat(s["data"]).replace(hour=int(m.group(1)), minute=int(m.group(2))) if m \
                else datetime.datetime.fromisoformat(s["data"])
        except ValueError:
            continue
        if agora - chegou > datetime.timedelta(hours=horas):
            por_hotel[s.get("hotel") or "?"] = por_hotel.get(s.get("hotel") or "?", 0) + 1
    if not por_hotel:
        return []
    n = sum(por_hotel.values())
    lista = ", ".join(f"{h} ({q})" for h, q in sorted(por_hotel.items(), key=lambda x: -x[1])[:4]) + ("…" if len(por_hotel) > 4 else "")
    return [{"nivel": "erro", "pc": "", "texto": f"{n} pedido(s) de formulário sem envio ao hotel há mais de {horas} h: {lista}. "
             "O robô copia e envia a cada 10 min; confira o Monitoramento (robô de envio e cópia dos hotéis)"}]


def mail_analytics_atrasado(ultimo_dia, hoje):
    """Último dia com dados de cada operador na planilha do Mail Analytics -> [aviso] de quem está 2+ dias atrás."""
    saida = []
    for agente, dia in sorted((ultimo_dia or {}).items()):
        try:
            d = datetime.date.fromisoformat(dia)
        except (TypeError, ValueError):
            continue
        if (hoje - d).days >= 2:
            saida.append({"nivel": "aviso", "pc": "", "texto": f"Mail Analytics: a planilha não tem dados de {agente} desde "
                          f"{d:%d/%m} (o relatório da semana fica incompleto)"})
    return saida
