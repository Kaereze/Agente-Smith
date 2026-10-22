"""Pedido por ligação (22/10/2026, opção B aprovada): botão "Ligação" no envio, etiqueta e filtro em Itens Enviados,
botão direito para marcar depois e cartão na Visão geral. Dados inventados."""
import datetime
import threading
from pathlib import Path

import pytest

import app_servidor
import espelho_emails
import ligacoes

UI = Path(__file__).resolve().parent.parent / "app_ui"
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")
CORREIO = (UI / "correio.js").read_text(encoding="utf-8")
ETIQUETA = (UI / "pecas" / "etiqueta.js").read_text(encoding="utf-8")


def ev(quando, chave, acao, agente="Clara", pc="PC-CLARA", hotel="EXEMPLO PRAIA"):
    return ligacoes.evento(chave, acao, agente, hotel, "nf@exemplo.com", "marina@exemplo.com", "NF 1",
                           pc=pc, quando=datetime.datetime.fromisoformat(quando))


def test_dobrar_vale_a_ultima_linha_e_guarda_o_dia_da_primeira_marca():
    linhas = [ligacoes.CABECALHO,
              ev("2026-10-20T10:00:00", "ENV-1", ligacoes.MARCAR),
              ev("2026-10-21T09:00:00", "ENV-1", ligacoes.DESMARCAR),
              ev("2026-10-22T08:00:00", "ENV-1", ligacoes.MARCAR, agente="João"),
              ev("2026-10-22T11:00:00", "ENV-2", ligacoes.MARCAR),
              ev("2026-10-22T11:05:00", "ENV-2", ligacoes.DESMARCAR),
              ["", "", "", ""], ["2026-10-22T12:00:00", "ENV-3", "OUTRA"]]
    m = ligacoes.dobrar(linhas)
    assert set(m) == {"ENV-1"}
    assert m["ENV-1"]["quando"].startswith("2026-10-20") and m["ENV-1"]["agente"] == "Clara"


def test_dobrar_sem_a_primeira_marca_nao_conta():   # a faxina apagou a marca de 400 dias atrás e ficou só o "tirar"
    assert ligacoes.dobrar([ligacoes.CABECALHO, ev("2026-10-22T08:00:00", "ENV-9", ligacoes.DESMARCAR)]) == {}


def test_resumo_hoje_semana_mes_e_listas():
    hoje = datetime.date(2026, 10, 22)
    linhas = [ligacoes.CABECALHO,
              ev("2026-10-22T09:00:00", "A", ligacoes.MARCAR, hotel="PRAIA", agente="Clara"),
              ev("2026-10-22T10:00:00", "B", ligacoes.MARCAR, hotel="PRAIA", agente="João"),
              ev("2026-10-16T10:00:00", "C", ligacoes.MARCAR, hotel="SERRA", agente="João"),   # 7º dia pra trás: entra
              ev("2026-10-15T10:00:00", "D", ligacoes.MARCAR, hotel="SERRA"),                  # fora dos 7 dias, no mês
              ev("2026-09-30T10:00:00", "E", ligacoes.MARCAR),                                 # mês passado
              ev("2026-10-23T10:00:00", "F", ligacoes.MARCAR)]                                 # relógio de outro PC adiantado
    r = ligacoes.resumo(ligacoes.dobrar(linhas), envios_hoje=9, hoje=hoje)
    assert (r["hoje"], r["semana"], r["mes"], r["envios_hoje"]) == (2, 3, 4, 9)
    assert r["por_hotel"] == [("PRAIA", 2), ("SERRA", 1)]
    assert r["por_agente"] == [("João", 2), ("Clara", 1)]


def test_chave_do_enviado_usa_o_id_do_envio_do_painel():
    assert ligacoes.chave_do_enviado({"id": "e1", "via": "painel|ENV-77"}) == "ENV-77"
    assert ligacoes.chave_do_enviado({"id": "e1", "via": "painel"}) == "e1"     # marca antiga, sem id
    assert ligacoes.chave_do_enviado({"id": "e2", "via": "outlook"}) == "e2"


class _Prop:
    def __init__(self, marca):
        self.marca = marca

    def GetProperty(self, _nome):
        if isinstance(self.marca, Exception):
            raise self.marca
        return self.marca


class _Item:
    def __init__(self, marca):
        self.PropertyAccessor = _Prop(marca)


@pytest.mark.parametrize("marca, via", [
    ("João|2026-10-22T10:00:00|ENV-123", "painel|ENV-123"),
    ("João|2026-10-22T10:00:00", "painel"),
    ("", "outlook"),
    (Exception("sem a propriedade"), "outlook"),
])
def test_via_do_item_leva_o_id_do_envio(marca, via):
    assert espelho_emails.via_do_item(_Item(marca)) == via


def test_envio_que_falhou_perde_a_marca_so_no_pc_que_marcou():
    m = ligacoes.dobrar([ligacoes.CABECALHO, ev("2026-10-22T09:00:00", "ENV-1", ligacoes.MARCAR, pc="PC1"),
                         ev("2026-10-22T09:00:00", "ENV-2", ligacoes.MARCAR, pc="PC2"),
                         ev("2026-10-22T09:00:00", "ENV-3", ligacoes.MARCAR, pc="PC1"),
                         ev("2026-10-22T09:00:00", "e-outlook", ligacoes.MARCAR, pc="PC1")])
    fila = {"ENV-1": {"resultado": "FALHOU"}, "ENV-2": {"resultado": "FALHOU"}, "ENV-3": {"resultado": "ENVIADO"}}
    assert ligacoes.envios_falhos_a_desmarcar(m, fila, "PC1") == ["ENV-1"]


class _Planilha:
    def __init__(self, falhar=False):
        self.linhas, self.falhar = [], falhar

    def anexar_linhas(self, _central, aba, linhas):
        if self.falhar:
            raise RuntimeError("cota")
        self.linhas += [(aba, list(l)) for l in linhas]


def _estado(falhar=False):
    e = object.__new__(app_servidor.Estado)
    e.backend, e.central, e.lock = _Planilha(falhar), "CENTRAL", threading.Lock()
    e.ligacoes_linhas, e.ligacoes, e.versao_tela = None, {}, 0
    e.enviados_correio = [{"id": "e1", "via": "painel|ENV-5", "hotel": "PRAIA", "caixa": "nf@p", "para": "h@x", "assunto": "NF 5"},
                          {"id": "e2", "via": "outlook", "hotel": "SERRA", "caixa": "nf@s", "para": "k@x", "assunto": "NF 6"}]
    return e


def test_envio_com_ligacao_grava_uma_linha_e_sem_ligacao_nenhuma():
    e = _estado()
    r = e._marcar_ligacao_do_envio({"ok": True, "id": "ENV-1"}, {"ligacao": True}, "Clara", "PRAIA", "nf@p", "h@x", "NF 1")
    assert r == {"ok": True, "id": "ENV-1"}
    assert [l[1][1:3] for l in e.backend.linhas] == [["ENV-1", ligacoes.MARCAR]] and e.backend.linhas[0][0] == ligacoes.ABA
    assert "ENV-1" in e.ligacoes and e.versao_tela == 1
    e._marcar_ligacao_do_envio({"ok": True, "id": "ENV-2"}, {}, "Clara", "PRAIA", "nf@p", "h@x", "NF 2")           # desligado
    e._marcar_ligacao_do_envio({"ok": False, "motivo": "x"}, {"ligacao": True}, "Clara", "PRAIA", "nf@p", "h@x", "NF 3")   # não saiu
    assert len(e.backend.linhas) == 1


def test_marca_que_nao_grava_nao_impede_o_envio_e_avisa():
    e = _estado(falhar=True)
    r = e._marcar_ligacao_do_envio({"ok": True, "id": "ENV-1"}, {"ligacao": True}, "Clara", "PRAIA", "nf@p", "h@x", "NF 1")
    assert r["ok"] and "Itens Enviados" in r["aviso_ligacao"]


def test_botao_direito_marca_pela_chave_certa_e_nao_repete():
    e = _estado()
    assert e.marcar_ligacao("e1", True, "João") == {"ok": True, "ligacao": True}
    assert e.marcar_ligacao("e1", True, "João") == {"ok": True, "ligacao": True}   # já marcado: nada novo na planilha
    e.marcar_ligacao("e2", True, "João")
    e.marcar_ligacao("e1", False, "João")
    assert [l[1][1:3] for l in e.backend.linhas] == [["ENV-5", ligacoes.MARCAR], ["e2", ligacoes.MARCAR], ["ENV-5", ligacoes.DESMARCAR]]
    assert set(e.ligacoes) == {"e2"}
    with pytest.raises(KeyError):
        e.marcar_ligacao("sumiu", True, "João")


def test_tela_botao_embaixo_do_enviar_comeca_desligado_e_vai_no_pedido():
    assert 'class="btn-lig" id="nf-lig" aria-pressed="false"' in PAINEL
    assert PAINEL.index('id="nf-ir"') < PAINEL.index('id="nf-lig"')
    assert PAINEL.count("ligacao: envNF.ligacao || undefined") == 2          # novo e-mail + responder/enviar NF
    assert "/api/correio/encaminhar\", { id: envNF.resp.id, para: $(\"nf-para\").value.trim(), corpo: $(\"nf-msg\").innerText,\n        selo: envNF.selo || undefined })" in PAINEL
    assert "rascunho.ligacao" in PAINEL and "function pecaLigacao" in ETIQUETA


def test_itens_enviados_lista_de_novo_com_etiqueta_filtro_e_botao_direito():
    assert ".filter(doEscopo)" not in CORREIO                               # o índice virava o "alvo" e a pasta ficava vazia
    assert 'ligacao: ["Só ligações"' in CORREIO and 'k !== "ligacao" || cx.caixa === "enviados"' in CORREIO
    assert '"/api/ligacao"' in CORREIO and "Marcar como ligação" in CORREIO
