import datetime

import atividade
import confirmar_nfs as c
import rede_pcs as r
from test_confirmar_nfs import sol

AGORA = datetime.datetime(2026, 10, 6, 18, 0, 0)


def test_comando_pra_este_pc_e_pra_todos_ate_ser_respondido():
    cab = [r.CAB_COMANDOS]
    p1 = r.pedido("PC-A", "atualizar", "João", AGORA - datetime.timedelta(minutes=5))
    p2 = r.pedido("TODOS", "atualizar", "João", AGORA - datetime.timedelta(minutes=2))
    p3 = r.pedido("PC-B", "atualizar", "João", AGORA)
    velho = r.pedido("PC-A", "atualizar", "João", AGORA - datetime.timedelta(hours=3))
    invalido = r.pedido("PC-A", "formatar", "João", AGORA)
    linhas = cab + [p1, p2, p3, velho, invalido]
    assert [x[0] for x in r.pendentes(linhas, "pc-a", AGORA)] == [p1[1], p2[1]]
    linhas.append(r.resposta(p2[1], "PC-A", "atualizar", "atualizando", AGORA))
    assert [x[0] for x in r.pendentes(linhas, "PC-A", AGORA)] == [p1[1]]
    assert [x[0] for x in r.pendentes(linhas, "PC-C", AGORA)] == [p2[1]]   # TODOS: cada PC responde por si


def test_lista_de_pcs_com_outlook_versao_e_conferencia():
    linhas = [["PC", "Agente", "Contas", "Visto em", "Outlook", "Versão", "Papel", "Última conferência"],
              ["PC-A", "João", "a@x,b@x", "2026-10-06 17:59:30", "aberto", "abc 06/10", "principal",
               "2026-10-06T17:58:00|2 NF · 0 tratativa · 1 recebido(s)"],
              ["PC-B", "Clara", "c@x", "2026-10-06 17:59:00", "fechado", "abc 06/10", "conferente", ""],
              ["PC-C", "Cristian", "d@x", "2026-10-06 17:59:50", "aberto", "old 01/10", "conferente",
               "2026-10-06T17:00:00|0 NF"],
              ["PC-D", "Bernardo", "e@x", "2026-10-05 09:00:00"]]
    pcs = {p["pc"]: p for p in r.ler_pcs(linhas, AGORA)}
    assert pcs["PC-A"]["online"] and pcs["PC-A"]["caixas"] == 2 and not pcs["PC-A"]["conferencia_atrasada"]
    assert pcs["PC-B"]["outlook"] == "fechado"
    assert pcs["PC-C"]["conferencia_atrasada"]            # Outlook aberto mas sem volta há 1 h
    assert not pcs["PC-D"]["online"]


def test_atividade_mais_nova_primeiro():
    linhas = [atividade.CABECALHO,
              atividade.linha(atividade.NF_ENVIADA, "BAHIA", "Ana", "NF 1", pc="PC-A", quando=AGORA),
              atividade.linha(atividade.TRATATIVA, "LUXOR", "Bia", "pergunta", pc="PC-B",
                              quando=AGORA + datetime.timedelta(minutes=1))]
    lidas = atividade.ler(linhas)
    assert [a["tipo"] for a in lidas] == [atividade.TRATATIVA, atividade.NF_ENVIADA] and lidas[1]["hotel"] == "BAHIA"


def test_email_sem_nota_ao_hospede_vira_tratativa():
    s = sol()
    reg = c.registro_da_central([s], {}, "2026-08-01")
    antes = set()
    ref = reg.aplicar_envio({"entry_id": "E9", "conta": "nf@barra.com", "destinatarios": {"maria@x.com"},
                             "assunto": "Dúvida sobre a sua nota", "data": datetime.datetime(2026, 9, 26, 10, 0),
                             "anexos": []}, ["pdf"])
    assert ref == (s["chave"], "tratativa")
    novas = c._novas_tratativas(reg, antes)
    assert [(k, e) for k, e, _ in novas] == [(s["chave"], "E9")]
    assert c.marca_do_email("E9") == c.marca_do_email("E9") and c.marca_do_email("E9").startswith("#")
