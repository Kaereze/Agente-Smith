"""Diário de envios: anota ANTES de enviar — base anti-duplicidade."""
import datetime
import json

from modelos import Hotel, Solicitacao
from arquivos import salvar_json

# Tempo pra considerar que um e-mail "sumido" realmente não saiu.
MINUTOS_ATE_DESISTIR = 10


class DiarioEnvios:
    def __init__(self, caminho):
        self.caminho = str(caminho)

    def listar(self):
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _salvar(self, entradas):
        salvar_json(self.caminho, entradas)

    def anotar(self, email, agora):
        entradas = self.listar()
        entradas.append({
            "codigo": email.codigo,
            "criado_em": agora.isoformat(timespec="seconds"),
            "destinatario": email.destinatario,
            "assunto": email.assunto,
            "solicitacoes": [{
                "planilha_id": s.hotel.planilha_id, "aba": s.hotel.aba, "hotel": s.hotel.nome,
                "operador": s.hotel.operador, "carimbo": s.carimbo, "email_hospede": s.email_hospede,
                "linha_bruta": [str(v) for v in s.linha_bruta], "assinatura": s.assinatura,
            } for s in email.solicitacoes],
        })
        self._salvar(entradas)

    def remover(self, codigos):
        codigos = set(codigos)
        if not codigos:
            return
        self._salvar([e for e in self.listar() if e["codigo"] not in codigos])


def solicitacoes_da_entrada(entrada):
    """Recria as solicitações a partir do diário (só o necessário pra marcar TRUE e registrar)."""
    resultado = []
    for d in entrada["solicitacoes"]:
        hotel = Hotel(aba=d["aba"], nome=d["hotel"], operador=d["operador"], planilha_id=d["planilha_id"])
        resultado.append(Solicitacao(hotel=hotel, linha=0, carimbo=d["carimbo"], email_hospede=d["email_hospede"],
                                     nome_titulo="", campos=[], linha_bruta=d.get("linha_bruta", []),
                                     assinatura=d.get("assinatura", "")))
    return resultado


def idade_minutos(entrada, agora):
    return (agora - datetime.datetime.fromisoformat(entrada["criado_em"])).total_seconds() / 60
