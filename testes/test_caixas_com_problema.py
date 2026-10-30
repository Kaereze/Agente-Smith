"""Botão de caixas com problema (27/10/2026): avisos marcados como "caixa", e-mails presos por conta, reinício do Outlook
e a peça de tela na paleta da Auditoria (sem verde)."""
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import outlook_vivo  # noqa: E402
import saude  # noqa: E402

UI = RAIZ / "app_ui"
HTML = (UI / "index.html").read_text(encoding="utf-8")
JS = (UI / "pecas" / "caixas.js").read_text(encoding="utf-8")
CSS = (UI / "pecas" / "caixas.css").read_text(encoding="utf-8")
SERVIDOR = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])


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
    assert 'url.path == "/api/caixas"' in SERVIDOR and 'path == "/api/outlook/reiniciar"' in SERVIDOR
    assert '"caixas": estado.rede_caixas' in SERVIDOR and '"reiniciar_outlook": estado.rede_reiniciar_outlook' in SERVIDOR


def test_a_peca_entra_na_pagina_e_o_x_so_guarda_o_quadro():
    assert '<link rel="stylesheet" href="/pecas/caixas.css">' in HTML and '<script src="/pecas/caixas.js"></script>' in HTML
    assert "window.caixasProblema?.(j.saude || [])" in HTML and '"/api/outlook/reiniciar"' in HTML
    assert "pn.hidden = true" in JS and "bt.hidden = pcs.size === 0" in JS   # o X guarda o quadro; o botão só some sem problema
    assert "limiteMs: 0" in JS                                                # o reinício abre a tela do K na hora


def test_cores_sao_as_da_auditoria_e_sem_verde():
    for cor in ("#0f6cbd", "#479ef5", "#c4314b", "#ff8d95", "#9a6700", "#f2c76b", "#e7f1fb", "#16324d"):
        assert cor in CSS
    for verde in ("#3ddc9e", "#5ec27e", "#08805a", "#107c41", "var(--verde", "var(--mata", "var(--ok"):
        assert verde not in CSS


def test_tela_do_k_tambem_usa_a_paleta_da_auditoria():
    k = (UI / "pecas" / "carregando.css").read_text(encoding="utf-8")
    for verde in ("var(--verde", "var(--mata", "var(--ok", "var(--chao", "var(--folha", "var(--linha"):
        assert verde not in k
    assert "var(--cp-azul)" in k and "var(--cp-verm)" in k


def test_classes_do_resultado_nao_colidem_com_as_do_painel():
    for antiga in ('"av"', '"ok"', '"er"', "cp-res an", "cp-lin a"):
        assert antiga not in JS.replace('"cp-azul"', "")
    for nova in ("cp-am", "cp-azul", "cp-verm", "cp-cinza", "cp-amb"):
        assert nova in JS and f".{nova}" in CSS or f".cp-res.{nova}" in CSS
