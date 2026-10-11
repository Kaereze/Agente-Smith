"""Saúde do sistema — uma faixa vermelha no topo do Painel quando algo sai do normal (usuário, 11/10/2026).

Motivo: a cópia das planilhas dos hotéis ficou 2,5 dias parada (08/10 21:36 a 11/10) e ninguém viu; e a Caixa de
Saída do Outlook já travou com 5 e-mails sem ninguém perceber. Cada PC publica na coluna "Saúde" da aba PCs_Painel
quantos e-mails estão presos na Caixa de Saída dele e (o PC principal) quando foi a última cópia que deu certo.
"""
import datetime

COPIA_ATRASADA_MIN = 75          # a cópia roda a cada 30 min: duas voltas perdidas + folga
SAIDA_TRAVADA_MIN = 10           # e-mail parado na Caixa de Saída há mais que isso
HORARIO_COPIA = ("07:00", "23:30")


def coluna(saida_travada, ultima_copia=""):
    """-> texto da coluna "Saúde" deste PC: "saida=2;copia=2026-10-11T13:14:38"."""
    partes = [f"saida={int(saida_travada or 0)}"]
    if ultima_copia:
        partes.append(f"copia={ultima_copia}")
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
    return sorted(saida, key=lambda x: x["nivel"] != "erro")
