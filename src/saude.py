"""Saúde do sistema — uma faixa vermelha no topo do Painel quando algo sai do normal (usuário, 11/10/2026).

Motivo: a cópia das planilhas dos hotéis ficou 2,5 dias parada (08/10 21:36 a 11/10) e ninguém viu; e a Caixa de
Saída do Outlook já travou com 5 e-mails sem ninguém perceber. Cada PC publica na coluna "Saúde" da aba PCs_Painel
quantos e-mails estão presos na Caixa de Saída dele e (o PC principal) quando foi a última cópia que deu certo.
"""
import datetime

COPIA_ATRASADA_MIN = 75          # a cópia roda a cada 30 min: duas voltas perdidas + folga
SAIDA_TRAVADA_MIN = 10           # e-mail parado na Caixa de Saída há mais que isso
HORARIO_COPIA = ("07:00", "23:30")


def coluna(saida_travada, ultima_copia="", sem_cadastro=(), robo=""):
    """-> texto da coluna "Saúde" deste PC: "saida=2;copia=2026-10-11T13:14:38;cad=CAMPO GRANDE|IDEAL;robo=iso"."""
    partes = [f"saida={int(saida_travada or 0)}"]
    if ultima_copia:
        partes.append(f"copia={ultima_copia}")
    if sem_cadastro:
        partes.append("cad=" + "|".join(str(x).replace(";", ",").replace("=", "-") for x in sem_cadastro))
    if robo:
        partes.append(f"robo={robo}")
    return ";".join(partes)


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
        elif p.get("conferencia_atrasada"):
            saida.append({"nivel": "aviso", "pc": p["pc"], "texto": f"Robô do PC de {quem} parado (sem conferir o Outlook há mais de 10 min)"})
        if versao_da_maioria and p.get("versao") and p["versao"] != versao_da_maioria and len(versoes) > 1:
            saida.append({"nivel": "aviso", "pc": p["pc"], "texto": f"PC de {quem} rodando outra versão ({p['versao']}): "
                          "use \"Atualizar todos os PCs\" em Máquinas"})
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
