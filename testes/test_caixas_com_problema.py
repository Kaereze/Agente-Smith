"""Botão de caixas com problema (27/10/2026): avisos marcados como "caixa", e-mails presos por conta, reinício do Outlook
e a peça de tela na paleta da Auditoria (sem verde)."""
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from emails import outlook_vivo  # noqa: E402
from painel import saude  # noqa: E402
from codigo_fonte import fonte_servidor

SERVIDOR = fonte_servidor(RAIZ)


def test_avisos_de_outlook_parado_levam_o_tipo_caixa():
    pcs = [{"pc": "PC1", "agente": "Cristian", "online": True, "saude": {"saida": 3, "mot": "senha"}, "outlook": "aberto"},
           {"pc": "PC2", "agente": "Clara", "online": True, "saude": {}, "outlook": "fechado"}]
    lista = saude.problemas(pcs, agora=datetime.datetime(2026, 10, 27, 10, 0))
    caixa = [p for p in lista if p.get("tipo") == "caixa"]
    assert {p["pc"] for p in caixa} == {"PC1", "PC2"}
    assert all(p.get("tipo") != "caixa" for p in lista if "versão" in p["texto"] or "Cadastro" in p["texto"])


class _Item:
    def __init__(self, minutos, conta):
        agora = datetime.datetime.now() - datetime.timedelta(minutes=minutos)
        self.LastModificationTime = agora
        self.SendUsingAccount = SimpleNamespace(SmtpAddress=conta, DisplayName=conta) if conta else None


class _Pasta:
    EntryID = "saida"

    def __init__(self, itens):
        self.Items = itens


def test_presos_por_conta_conta_so_os_parados_e_separa_por_caixa():
    pasta = _Pasta([_Item(30, "nota@redeandradecampogrande.com.br"), _Item(40, "nota@redeandradecampogrande.com.br"),
                    _Item(35, "nota@redeandradeondina.com.br"), _Item(1, "nota@redeandradeondina.com.br"), _Item(50, None)])
    ns = SimpleNamespace(GetDefaultFolder=lambda n: pasta, Accounts=[])
    r = {c["caixa"]: c["presos"] for c in saude.presos_por_conta(ns)}
    assert r == {"CAMPOGRANDE": 2, "ONDINA": 1, "SEM CONTA DEFINIDA": 1}   # o de 1 min não conta: ainda está saindo


def test_reiniciar_em_teste_nao_mata_nenhum_outlook():
    assert outlook_vivo.reiniciar() == {"ok": True, "segundos": 0, "saiu": 0, "presos": 0}


def test_servidor_tem_as_rotas_do_botao():
    assert '"/api/caixas"' in SERVIDOR and '"/api/outlook/reiniciar"' in SERVIDOR
    assert '"caixas": estado.rede_caixas' in SERVIDOR and '"reiniciar_outlook": estado.rede_reiniciar_outlook' in SERVIDOR


