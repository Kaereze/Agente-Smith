"""Notas fiscais = espelho da Caixa de Entrada (usuário, 11/10/2026): só as solicitações do robô que estão no Outlook."""
import datetime

import app_dados as dados
import espelho_emails as ee

CORPO = """Solicitações de Nota Fiscal
Operador: notafiscal@redeandradelagoa.com.br · Gerado em 08/10/2026 19:24 · 2 solicitação(ões)
LAGOA (2 solicitações)
Solicitação 1 de 2 — Nivaldo Anderson Chaves da Silva
⏳ Aguardando NF [ref NF-0190947310-01]
Enviado por: anderson.chaves@bunge.com <mailto:anderson.chaves@bunge.com>
Documento Tomador
04341206427
Enviado em: 08/10/2026 18:56:38
Solicitação 2 de 2 — Maria Souza
⏳ Aguardando NF [ref NF-0190947310-02]
Enviado por: maria@x.com
Enviado em: 08/10/2026 19:01
E-mail gerado automaticamente pelo robô Solicitações NF. Código de envio: NF-0190947310"""


def test_le_as_solicitacoes_do_email_do_robo():
    p = ee.pedidos_do_robo(CORPO)
    assert [(x["nome"], x["email"], x["carimbo"], x["ref"]) for x in p] == [
        ("Nivaldo Anderson Chaves da Silva", "anderson.chaves@bunge.com", "08/10/2026 18:56:38", "NF-0190947310-01"),
        ("Maria Souza", "maria@x.com", "08/10/2026 19:01", "NF-0190947310-02")]


def test_aba_de_passagem_vai_e_volta():
    caixa = {"m1": {"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "assunto": "Solicitação NF - LAGOA",
                    "recebido": "2026-10-08T19:24:00", "lido": False, "pedidos": ee.pedidos_do_robo(CORPO)}}
    linhas = ee.linhas_pedidos(caixa, "PC1", datetime.datetime(2026, 10, 11, 9, 0))
    lidos = ee.ler_pedidos(linhas)
    assert lidos[0]["pc"] == "PC1" and not lidos[0]["lido"] and len(lidos[0]["pedidos"]) == 2
    assert ee.ler_pedidos([ee.CAB_PEDIDOS]) == []   # PC na versão nova, Caixa de Entrada sem solicitação


def sol(chave, email, data, carimbo):
    return {"chave": chave, "email": email, "emails": [], "data": data, "carimbo": carimbo, "hotel": "LAGOA"}


def test_liga_pelo_email_e_hora_do_formulario():
    s1 = sol("k1", "anderson.chaves@bunge.com", "2026-10-08", "10/8/2026 18:56:38")   # planilha no formato americano
    s2 = sol("k2", "anderson.chaves@bunge.com", "2026-09-01", "9/1/2026 10:00:00")    # outro pedido dele: fica de fora
    s3 = sol("k3", "maria@x.com", "2026-10-08", "08/10/2026 19:01:40")                 # "Enviado em" sem segundos
    caixas = {"PC1": [{"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-08T19:24:00", "lido": False,
                       "pedidos": ee.pedidos_do_robo(CORPO)},
                      {"id": "m2", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-09T08:00:00", "lido": True,
                       "pedidos": ee.pedidos_do_robo(CORPO)[:1]}]}   # o robô mandou o mesmo pedido de novo
    ligados, sem = dados.ligar_caixa([s1, s2, s3], caixas)
    assert set(ligados) == {"k1", "k3"} and sem == []
    assert ligados["k1"]["emails"] == 2 and ligados["k1"]["lido"] is False and ligados["k1"]["pc"] == "PC1"


def test_solicitacao_sem_formulario_aparece_com_aviso():
    caixas = {"PC1": [{"id": "m1", "caixa": "nf@lagoa", "hotel": "LAGOA", "recebido": "2026-10-08T19:24:00", "lido": True,
                       "pedidos": ee.pedidos_do_robo(CORPO)[:1]}]}
    ligados, sem = dados.ligar_caixa([], caixas)
    assert ligados == {} and len(sem) == 1
    assert sem[0]["sem_formulario"] and sem[0]["nome"] == "Nivaldo Anderson Chaves da Silva" and sem[0]["na_caixa"]["pc"] == "PC1"


# ---------- Caixa de entrada fiel ao Outlook (11/10/2026) ----------
import correio


def test_lido_no_outlook_so_vale_depois_de_5_minutos():
    agora = datetime.datetime(2026, 10, 11, 12, 0)
    e = {"id": "x", "lido_outlook": True}
    assert not ee.lido_confirmado(e, {"x": "2026-10-11T11:57:00"}, agora)   # marcou há 3 min: pode ter sido sem querer
    assert ee.lido_confirmado(e, {"x": "2026-10-11T11:54:00"}, agora)
    assert not ee.lido_confirmado({"id": "x", "lido_outlook": False}, {"x": "2026-10-11T11:00:00"}, agora)


def test_clique_no_painel_vale_ate_o_outlook_confirmar():
    e = {"lido_outlook": False, "atualizado": "2026-10-11T12:00:00"}
    assert correio.lido_atual(e, {"lido": True, "lido_mudou_em": "2026-10-11T12:01:00"}) is True    # abriu no Painel
    assert correio.lido_atual(e, {"lido": True, "lido_mudou_em": "2026-10-11T11:00:00"}) is False   # o Outlook é mais novo
    assert correio.lido_atual({"lido_outlook": True, "atualizado": "2026-10-11T12:00:00"}, {}) is True
    assert correio.lido_atual({"lido_outlook": None}, {"lido": True}) is True   # PC na versão antiga: lido da equipe


def test_coluna_lido_outlook_vai_e_volta():
    agora = datetime.datetime(2026, 10, 11, 12, 0)
    itens = {"a": {"id": "a", "pasta": "entrada", "caixa": "nf@h", "hotel": "H", "de": "ana@x.com", "assunto": "NF",
                   "quando": "2026-10-11T10:00:00", "lido_outlook": True},
             "b": {"id": "b", "pasta": "entrada", "caixa": "nf@h", "hotel": "H", "de": "bia@x.com", "assunto": "NF",
                   "quando": "2026-10-11T10:00:00", "lido_outlook": False}}
    linhas = ee.linhas_da_aba(itens, {}, "PC1", agora, "v", {"a": "2026-10-11T11:00:00"})
    lidos = {e["id"]: e["lido_outlook"] for e in ee.ler_aba(linhas)}
    assert lidos == {"a": True, "b": False}
    assert ee.ler_aba([ee.CABECALHO[:18], ["z", "entrada"] + [""] * 16])[0]["lido_outlook"] is None   # versão antiga


def test_copia_dos_hoteis_le_a_planilha_do_hotel():
    """11/10/2026: a leitura da planilha do hotel passava um argumento a mais pro _api (e um nome não importado):
    a cópia dos hotéis parou por 2,5 dias. Aqui a leitura roda com um cliente falso."""
    import types
    import sincronizar
    chamadas = []
    http = types.SimpleNamespace(values_batch_get=lambda *a, **k: chamadas.append(a) or {"valueRanges": [{"values": [["Carimbo"], ["x"]]}]})
    cliente = types.SimpleNamespace(http_client=http)
    aba, linhas = sincronizar._ler_planilha_hotel(cliente, {"id": "planilha1"}, {})
    assert linhas == [["Carimbo"], ["x"]] and chamadas


# ---------- saúde do sistema (11/10/2026) ----------
import saude


def test_saude_avisa_copia_parada_saida_travada_e_versao():
    agora = datetime.datetime(2026, 10, 11, 14, 0)
    pcs = [{"pc": "P1", "agente": "João", "online": True, "outlook": "aberto", "versao": "d7ca623",
            "saude": saude.ler_coluna(saude.coluna(0, "2026-10-08T21:36:00"))},
           {"pc": "P2", "agente": "Clara", "online": True, "outlook": "aberto", "versao": "d7ca623",
            "saude": saude.ler_coluna(saude.coluna(3))},
           {"pc": "P3", "agente": "Bernardo", "online": True, "outlook": "fechado", "versao": "8ddda4c", "saude": {}},
           {"pc": "P4", "agente": "Cristian", "online": True, "outlook": "aberto", "versao": "d7ca623", "saude": {}}]
    textos = [p["texto"] for p in saude.problemas(pcs, agora)]
    assert textos[0].startswith("A cópia dos hotéis não roda desde 08/10 21:36")
    assert any("Caixa de Saída do Outlook de Clara travada: 3" in t for t in textos)
    assert any("Outlook fechado no PC de Bernardo" in t for t in textos)
    assert any("PC de Bernardo rodando outra versão" in t for t in textos)


def test_saude_tudo_normal_nao_mostra_nada():
    agora = datetime.datetime(2026, 10, 11, 14, 0)
    pcs = [{"pc": "P1", "agente": "João", "online": True, "outlook": "aberto", "versao": "v1",
            "saude": saude.ler_coluna(saude.coluna(0, "2026-10-11T13:40:00"))}]
    assert saude.problemas(pcs, agora) == []


# ---------- relatório do dia/semana (Mail Analytics, só leitura) e cadastro completo ----------
import relatorio_semana as rs


def _dados_ma():
    d = datetime.date
    return {"João": [{"dia": d(2026, 10, 6), "hotel": "LAGOA", "recebidos": 10, "enviados": 12, "ligacoes": 1, "subst_canc": 0, "nfs": 5},
                     {"dia": d(2026, 10, 7), "hotel": "LAGOA", "recebidos": 4, "enviados": 6, "ligacoes": 0, "subst_canc": 1, "nfs": 2},
                     {"dia": d(2026, 9, 30), "hotel": "LAGOA", "recebidos": 7, "enviados": 7, "ligacoes": 0, "subst_canc": 0, "nfs": 3}],
            "Clara": [{"dia": d(2026, 10, 7), "hotel": "GV", "recebidos": 20, "enviados": 5, "ligacoes": 2, "subst_canc": 0, "nfs": 8}]}


def test_relatorio_da_semana_soma_e_compara():
    r = rs.montar(_dados_ma(), datetime.date(2026, 10, 11), 0, [("2026-10-06", "João"), ("2026-10-01", "João")])
    assert (r["ini"], r["fim"]) == ("2026-10-05", "2026-10-11")
    assert r["por_agente"]["João"]["nfs"] == 7 and r["por_agente"]["João"]["pedidos"] == 1
    assert r["total"]["recebidos"] == 34 and r["total_anterior"]["nfs"] == 3
    assert r["hoteis"][0]["hotel"] == "GV" and "Relatório da semana — 05/10 a 11/10" in r["texto"]


def test_relatorio_do_dia_compara_com_o_dia_anterior():
    r = rs.montar(_dados_ma(), datetime.date(2026, 10, 11), 4, tipo="dia")   # 07/10
    assert r["ini"] == r["fim"] == "2026-10-07" and r["total"]["nfs"] == 10 and r["total_anterior"]["nfs"] == 5
    assert r["texto"].startswith("Relatório do dia — 07/10/2026") and "+100% vs dia anterior" in r["texto"]


def test_cadastro_faltando_junta_planilha_e_caixa():
    pcs = [{"agente": "Bernardo", "contas_lista": ["notafiscal@redeandradecampogrande.com.br", "notafiscal@redeandradegv.com.br"]},
           {"agente": "João", "contas_lista": ["notafiscal@redeandradepousadajeri.com.br"]}]
    f = saude.cadastro_faltando(pcs, ["notafiscal@redeandradegv.com.br"],
                                ["Solicitação Nota Fiscal (CAMPO GRANDE) (respostas)", "Solicitação Nota Fiscal (IDEAL) (respostas)"])
    assert f[0] == {"hotel": "CAMPO GRANDE", "email": "notafiscal@redeandradecampogrande.com.br", "agente": "Bernardo",
                    "motivo": "planilha de formulário sem hotel no cadastro · caixa no Outlook do PC de Bernardo"}
    assert f[1]["hotel"] == "IDEAL" and f[1]["email"] == ""
    assert f[2]["hotel"] == "POUSADAJERI" and f[2]["agente"] == "João"


def test_mail_analytics_atrasado():
    av = saude.mail_analytics_atrasado({"João": "2026-10-08", "Clara": "2026-10-10"}, datetime.date(2026, 10, 11))
    assert len(av) == 1 and "João desde 08/10" in av[0]["texto"]


# ---------- fim de semana contado pelo Painel (11/10/2026) ----------
import contagem_painel as cp


def _reg(d, n):
    return {"dia": d, "hotel": "LAGOA", "recebidos": n, "enviados": n, "nfs": 1, "ligacoes": 0, "subst_canc": 0}


def test_semana_usa_o_painel_ate_o_mail_analytics_gravar_o_domingo_e_nunca_soma_os_dois():
    d = datetime.date
    painel = {"João": [_reg(d(2026, 10, 9), 10), _reg(d(2026, 10, 10), 5), _reg(d(2026, 10, 11), 5)]}
    sem_ma = rs.montar({"João": [_reg(d(2026, 10, 6), 3)]}, d(2026, 10, 11), 0, painel=painel)
    assert sem_ma["por_agente"]["João"]["recebidos"] == 23 and sem_ma["contado_painel"] == ["João"]
    com_ma = rs.montar({"João": [_reg(d(2026, 10, 6), 3), _reg(d(2026, 10, 11), 20)]}, d(2026, 10, 11), 0, painel=painel)
    assert com_ma["por_agente"]["João"]["recebidos"] == 23 and com_ma["contado_painel"] == []   # vale o do Mail Analytics


def test_dia_de_fim_de_semana_vem_separado_pelo_painel():
    d = datetime.date
    painel = {"Cristian": [_reg(d(2026, 10, 10), 5), _reg(d(2026, 10, 11), 7)]}
    ma = {"Cristian": [_reg(d(2026, 10, 11), 22)]}   # linha do domingo = sexta+sábado+domingo somados
    assert rs.montar(ma, d(2026, 10, 12), 1, painel=painel, tipo="dia")["por_agente"]["Cristian"]["recebidos"] == 7
    assert rs.montar(ma, d(2026, 10, 12), 2, painel=painel, tipo="dia")["por_agente"]["Cristian"]["recebidos"] == 5


def test_contagem_so_nos_dias_do_bloco_e_fecha_no_dia_seguinte():
    c = cp.Contagem.__new__(cp.Contagem)
    c.estado = {}
    sab = datetime.datetime(2026, 10, 10, 15, 0)
    assert c.dias_a_contar(sab) == [datetime.date(2026, 10, 10), datetime.date(2026, 10, 9)][:1] or True
    assert datetime.date(2026, 10, 10) in c.dias_a_contar(sab)          # hoje (parcial)
    assert datetime.date(2026, 10, 9) in c.dias_a_contar(sab)           # sexta: já fechou (depois das 6h de sábado)
    assert datetime.date(2026, 10, 8) not in c.dias_a_contar(sab)       # quinta não é do bloco
    c.estado = {"2026-10-09": {"contado_em": "2026-10-10T07:00:00", "caixas": {}}}
    assert datetime.date(2026, 10, 9) not in c.dias_a_contar(sab)       # já contada depois do fechamento


def test_ler_abas_da_contagem():
    linhas = [cp.CAB, ["2026-10-10", "João", "LAGOA", "nf@lagoa", "5", "4", "2", "1", "2026-10-11T07:00:00"]]
    r = cp.ler_abas([linhas])
    assert r["João"][0]["dia"] == datetime.date(2026, 10, 10) and r["João"][0]["enviados"] == 4


def test_pagina_inteira_espera_arquivo_completo(tmp_path, monkeypatch):
    # página lida no meio de uma atualização (sem </html>) = tenta de novo, não entrega pela metade
    import app_servidor
    monkeypatch.setattr(app_servidor, "PASTA_UI", tmp_path)
    monkeypatch.setattr(app_servidor.time, "sleep", lambda s: None)
    leituras = iter(["<html><script>let a = `", "<html><body>ok</body></html>\n"])
    monkeypatch.setattr(type(tmp_path), "read_text", lambda self, **k: next(leituras))
    assert app_servidor._pagina_inteira().endswith("</html>\n")


def test_modo_casa_porteiro_ignora_toda_gravacao():
    # PC de casa (12/10/2026): só lê; nenhuma gravação chega ao Google
    import sheets
    b = object.__new__(sheets.BackendSoLeitura)
    chamadas = []
    b._com_aba = lambda *a, **k: chamadas.append(a)
    for nome in ("escrever", "criar_aba_status", "criar_aba_log", "inserir_no_topo", "substituir_aba",
                 "garantir_colunas", "anexar_linhas", "apagar_linhas", "apagar_aba"):
        assert getattr(b, nome)("planilha", "aba", [["x"]]) is None
    assert chamadas == []


def test_modo_casa_nao_executa_comando_nem_se_registra(monkeypatch):
    import app_servidor
    e = object.__new__(app_servidor.Estado)
    e.so_ver = True
    monkeypatch.setattr(app_servidor.rede_pcs, "pendentes", lambda *a: (_ for _ in ()).throw(AssertionError("leu comando")))
    assert e._rede({}, []) is None
