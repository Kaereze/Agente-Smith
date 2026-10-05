import datetime

import app_dados as d
import fiscal_intelligence as fi
import painel_metricas as pm
from hoteis import CadastroHoteis

CAD = CadastroHoteis([["CRICIÚMA", "nf@cri.com", "Cristian"], ["GOIÂNIA CENTRO", "nf@goi.com", "Clara"],
                      ["SÃO FRANCISCO", "nf@sf.com", "João"], ["Nome", "Email", "Operador"]],
                     {"GOIÂNIA": "GOIÂNIA CENTRO"})
D = datetime.date
CAB = ["Data", "Hotel", "Emails Recebidos", "Emails Enviados", "Ligações", "Substituições/Cancelamentos", "NFs Emitidas"]


def test_cadastro_casa_acento_caixa_apelido_e_espaco():
    assert CAD.canonico("criciuma") == "CRICIÚMA"
    assert CAD.canonico("São Francisco") == "SÃO FRANCISCO"
    assert CAD.canonico("Goiânia") == "GOIÂNIA CENTRO"
    assert CAD.canonico("SAOFRANCISCO") == "SÃO FRANCISCO"
    assert CAD.canonico("Outro") is None
    assert CAD.dados("CRICIÚMA")["agente"] == "Cristian"
    assert "Nome" not in CAD.nomes()


def test_metricas_branco_e_zero_repetido_vale_a_ultima_e_respeita_desde():
    linhas = [CAB, [], ["31/08/2026", "CRICIUMA", "9", "9", "9", "9", "9"],
              ["01/09/2026", "CRICIUMA", "3", "2", "", "1", ""],
              ["01/09/2026", "CRICIUMA", "5", "4", "1", "0", "2"],
              ["02/09/2026", "HOTEL NOVO", "1", "0", "0", "0", "0"]]
    regs, avisos = fi.ler_metricas(linhas, "Cristian", CAD, D(2026, 9, 1))
    por = {(r["data"], r["hotel"]): r for r in regs}
    assert len(regs) == 2
    assert por[(D(2026, 9, 1), "CRICIÚMA")]["recebidos"] == 5 and por[(D(2026, 9, 1), "CRICIÚMA")]["nfs"] == 2
    assert any("repetido" in a for a in avisos) and any("HOTEL NOVO" in a for a in avisos)


def test_cabecalho_sem_as_ultimas_colunas_usa_a_posicao():
    regs, _ = fi.ler_metricas([CAB[:5], ["01/09/2026", "CRICIUMA", "1", "2", "3", "4", "5", "09/2026", "Com NF"]],
                              "João", CAD, D(2026, 9, 1))
    assert (regs[0]["cancelamentos"], regs[0]["nfs"]) == (4, 5)


def test_fins_de_semana_somados_e_guardados():
    log = [["Quando", "Operador", "Evento", "Detalhe"],
           ["", "João", "FIM_DE_SEMANA_SOMADO", "20/09/2026: sex 18/09 + sáb 19/09 + dom 20/09 somados — ok"],
           ["", "Clara", "FIM_DE_SEMANA_SOMADO", "13/09/2026: sex+sáb+dom somados"],
           ["", "João", "FIM_DE_SEMANA_GUARDADO", "18/09/2026 guardado pra somar no domingo 20/09/2026"]]
    somados, guardados = fi.fins_de_semana(log)
    assert somados[("João", D(2026, 9, 20))] == "sex 18/09 + sáb 19/09 + dom 20/09"
    assert somados[("Clara", D(2026, 9, 13))] == "fim de semana somado"
    assert guardados[("João", D(2026, 9, 18))] == D(2026, 9, 20)


def test_saude_ontem_e_sinal_do_escutar_comando():
    hoje, agora = D(2026, 9, 19), datetime.datetime(2026, 9, 19, 10, 0, 30)
    metricas = [{"operador": "Clara", "data": D(2026, 9, 18)}]
    abas = {"Status_Execucao": [["Operador", "Última Atualização", "Status", "Detalhe"], ["Cristian", "", "ATENCAO", "x"]],
            "Status_Operadores": [["Operador", "Última Execução Bem-Sucedida"], ["João", "19/09/2026 07:01:49"]],
            "Painel_Controle": [["t"], ["Comando:", "OCIOSO", "18/09/2026", "", "2026-09-19 10:00:10"], ["Status:", "ok"]]}
    s = fi.saude(abas, metricas, {("João", D(2026, 9, 18)): D(2026, 9, 20)}, hoje, agora)
    por = {o["operador"]: o for o in s["operadores"]}
    assert por["Clara"]["ontem"] == "puxado" and por["João"]["ontem"] == "guardado" and por["Bernardo"]["ontem"] == "nao_puxado"
    assert por["Cristian"]["status"] == "ATENCAO"
    assert s["escutar_comando"]["online"] is True and s["escutar_comando"]["ultimo_consolidado"] == "18/09/2026"
    abas["Painel_Controle"][1][4] = "2026-09-19 09:50:00|DESATUALIZADO"
    e = fi.saude(abas, metricas, {}, hoje, agora)["escutar_comando"]
    assert e["online"] is False and e["desatualizado"] is True


DETALHE_CRISTIAN = ("1 hotel(is) do cadastro não conectaram hoje: RENASSENÇA — confira o e-mail cadastrado; "
                    "🚨 Linhas duplicadas encontradas em 'Agente_Cristian' (NÃO apagadas — decisão humana): "
                    "05/08/2026 | HANGAR (2 linhas); 05/08/2026 | VERNON (2 linhas)")


def test_avisos_de_hotel_ignorado_e_de_antes_do_periodo_saem():
    ficam, saem = fi.filtrar_avisos(DETALHE_CRISTIAN, ["Renassença"], D(2026, 9, 1))
    assert ficam == [] and len(saem) == 3
    ficam, _ = fi.filtrar_avisos("1 hotel(is) do cadastro não conectaram hoje: RENASSENÇA, LAPA — x", ["RENASSENÇA"], D(2026, 9, 1))
    assert len(ficam) == 1   # outro hotel junto: o aviso continua
    ficam, _ = fi.filtrar_avisos("Outlook travou em 12/09/2026", ["RENASSENÇA"], D(2026, 9, 1))
    assert ficam == ["Outlook travou em 12/09/2026"]


def test_operador_so_com_avisos_ignorados_fica_ok():
    abas = {"Status_Execucao": [["Operador", "Última Atualização", "Status", "Detalhe"],
                                ["Cristian", "", "ATENCAO", DETALHE_CRISTIAN]]}
    s = fi.saude(abas, [], {}, D(2026, 10, 1), datetime.datetime(2026, 10, 1, 10), ["RENASSENÇA"], D(2026, 9, 1))
    cristian = next(o for o in s["operadores"] if o["operador"] == "Cristian")
    assert cristian["status"] == "OK" and cristian["detalhe"] == "" and cristian["avisos_ignorados"] == 3


def test_lacuna_conhecida_nao_gera_aviso():
    detalhe = "2 dia(s) sem dado nos últimos 30 em 'Agente_Cristian': 27/09/2026, 06/09/2026 — não recuperado"
    lac = fi.lacunas_por_operador({"*": ["06/09/2026"], "Cristian": ["25/09/2026", "26/09/2026", "27/09/2026"]})
    assert lac["Clara"] == {D(2026, 9, 6)} and D(2026, 9, 27) in lac["Cristian"]
    assert fi.filtrar_avisos(detalhe, (), D(2026, 9, 1), lac["Cristian"])[0] == []
    assert fi.filtrar_avisos(detalhe, (), D(2026, 9, 1), lac["Clara"])[0] == [detalhe]   # 27/09 não é lacuna dela
    abas = {"Status_Execucao": [["Operador", "Última Atualização", "Status", "Detalhe"], ["Cristian", "", "ATENCAO", detalhe]]}
    s = fi.saude(abas, [], {}, D(2026, 10, 1), datetime.datetime(2026, 10, 1, 10), (), D(2026, 9, 1), lac)
    assert next(o for o in s["operadores"] if o["operador"] == "Cristian")["status"] == "OK"


def test_tabela_sem_hotel_ignorado():
    t = pm.tabela_hoteis([], [], D(2026, 9, 1), D(2026, 9, 30), D(2026, 9, 30), CAD, ignorar={"SÃO FRANCISCO"})
    assert "SÃO FRANCISCO" not in {l["hotel"] for l in t}


def _sol(hotel, data, situacao):
    return {"chave": hotel + data + situacao, "hotel": hotel, "data": data, "situacao": situacao, "nome": "x", "dono": ""}


def _met(hotel, data, **v):
    return {"hotel": hotel, "data": data, "operador": "João", **{m: v.get(m, 0) for m in fi.METRICAS}}


def test_visao_geral_e_tabela_de_hoteis():
    hoje = D(2026, 9, 30)
    fila = [_sol("CRICIÚMA", "2026-09-29", d.CONCLUIDA), _sol("CRICIÚMA", "2026-09-28", d.NA_FILA),
            _sol("CRICIÚMA", "2026-09-10", d.NA_FILA), _sol("SÃO FRANCISCO", "2026-09-29", d.EM_TRATAMENTO)]
    metr = [_met("CRICIÚMA", D(2026, 9, 29), nfs=4, cancelamentos=1, recebidos=3), _met("CRICIÚMA", D(2026, 8, 30), nfs=99)]
    v = pm.visao_geral(metr, fila, D(2026, 9, 25), D(2026, 9, 30), hoje, {})
    assert v["kpis"]["solicitacoes"] == 3 and v["kpis"]["concluidas"] == 1 and v["kpis"]["taxa_atendimento"] == 33
    assert v["kpis"]["pendentes_agora"] == 3 and v["kpis"]["pendentes_7d"] == 1
    assert v["kpis"]["nfs"] == 4 and len(v["serie"]) == 6
    assert {i["faixa"]: i["n"] for i in v["idade"]}["16–30 dias"] == 1
    assert v["top_pendentes"][0] == {"hotel": "CRICIÚMA", "n": 2}
    t = {l["hotel"]: l for l in pm.tabela_hoteis(metr, fila, D(2026, 9, 25), D(2026, 9, 30), hoje, CAD)}
    assert t["CRICIÚMA"]["pendentes"] == 2 and t["CRICIÚMA"]["mais_antigo"] == 20
    assert t["CRICIÚMA"]["taxa_cancelamento"] == 25 and t["CRICIÚMA"]["agente"] == "Cristian"
    assert t["GOIÂNIA CENTRO"]["solicitacoes"] == 0   # hotel do cadastro aparece mesmo sem dado


def test_serie_marca_domingo_somado():
    s = pm.serie_diaria([_met("CRICIÚMA", D(2026, 9, 20), nfs=5)], [], D(2026, 9, 19), D(2026, 9, 20),
                        {("João", D(2026, 9, 20)): "sex 18/09 + sáb 19/09 + dom 20/09"})
    assert s[0]["fim_de_semana"] == [] and s[1]["fim_de_semana"] == ["João: sex 18/09 + sáb 19/09 + dom 20/09"]


AVISO_SOMA = ("⚠️ Fim de semana de 04/10/2026 somado SEM sábado 03/10 (dia não contado nesta máquina) em 18 hotel(is). "
              "Pra completar: python src\main.py --data=2026-10-03")


def test_quem_nao_soma_fim_de_semana_nao_recebe_aviso_de_soma_incompleta():
    abas = {"Status_Execucao": [["Operador", "Última Atualização", "Status", "Detalhe"],
                                ["Clara", "", "ATENCAO", AVISO_SOMA], ["João", "", "ATENCAO", AVISO_SOMA]]}
    s = fi.saude(abas, [], {}, D(2026, 10, 5), datetime.datetime(2026, 10, 5, 10), (), D(2026, 9, 1), None,
                 ["João", "Cristian"])
    por = {o["operador"]: o for o in s["operadores"]}
    assert por["Clara"]["status"] == "OK" and por["Clara"]["detalhe"] == ""
    assert por["João"]["status"] == "ATENCAO" and "somado SEM" in por["João"]["detalhe"]   # pra quem soma, vale


def test_fim_de_semana_sem_dado_e_dia_a_mais_pra_quem_nao_soma():
    domingo_seguinte = D(2026, 10, 5)   # segunda: ontem foi domingo
    s = fi.saude({}, [], {}, domingo_seguinte, datetime.datetime(2026, 10, 5, 10), somam_fim_de_semana=["João", "Cristian"])
    por = {o["operador"]: o for o in s["operadores"]}
    assert por["Bernardo"]["ontem"] == "fim_de_semana" and por["Cristian"]["ontem"] == "nao_puxado"
    terca = fi.saude({}, [], {}, D(2026, 10, 7), datetime.datetime(2026, 10, 7, 10), somam_fim_de_semana=["João"])
    assert {o["operador"]: o["ontem"] for o in terca["operadores"]}["Bernardo"] == "nao_puxado"   # dia útil cobra
