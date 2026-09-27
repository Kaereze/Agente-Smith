"""Roteiro de testes do robô inteiro, com Google e Outlook falsos."""
import datetime
import os

from conftest import AGORA, ARACAJU, BARRA, CABECALHO_HOTEL, CENTRAL, ESTRELA, Relogio, linha_hotel
from main import executar
from sheets import marcar_enviados, ler_hoteis, ler_pendentes


def _coluna_enviado(planilha, aba):
    i = CABECALHO_HOTEL.index("Enviado")
    return [l[i] if len(l) > i else "" for l in planilha.aba(aba)[1:]]


def _rodar(cfg, planilha, outlook, agora=AGORA, relogio=None):
    relogio = relogio or Relogio()
    return executar(cfg, planilha, outlook, esperar=relogio.esperar, agora=agora, relogio=relogio.agora)


def test_envio_normal_agrupa_por_operador_e_marca_true(cfg, planilha, outlook):
    assert _rodar(cfg, planilha, outlook) == 0

    assert len(outlook.enviados) == 2                     # 2 operadores -> 2 e-mails
    op1 = next(e for e in outlook.enviados if e.operador == "notafiscal1@andradehoteis.com.br")
    assert [s.hotel.nome for s in op1.solicitacoes] == ["BARRA", "ESTRELA CENTRO", "ESTRELA CENTRO"]
    assert op1.assunto == "Solicitações NF (3) - BARRA, ESTRELA CENTRO"

    assert _coluna_enviado(planilha, ESTRELA) == ["TRUE", "TRUE", "TRUE"]   # vazio também conta como pendente
    assert _coluna_enviado(planilha, ARACAJU) == ["TRUE"]
    assert len(planilha.aba("Registros", "REGISTROS")) == 1 + 4             # registro central
    status = dict((l[0], l[1]) for l in planilha.aba("Status"))
    assert status["Última execução com sucesso"] == "24/09/2026 10:00:00"


def test_rodar_duas_vezes_nao_duplica(cfg, planilha, outlook):
    _rodar(cfg, planilha, outlook)
    _rodar(cfg, planilha, outlook)
    chaves = outlook.solicitacoes_enviadas()
    assert len(chaves) == 4 and len(set(chaves)) == 4
    assert len(outlook.enviados) == 2


def test_painel_desligado_nao_envia(cfg, planilha, outlook):
    planilha.aba("Status")[0][1] = "FALSE"
    assert _rodar(cfg, planilha, outlook) == 0
    assert outlook.enviados == []
    assert "FALSE" in _coluna_enviado(planilha, ARACAJU)


def test_sem_aba_status_cria_desligado(cfg, planilha, outlook):
    del planilha.planilhas[CENTRAL]["Status"]
    _rodar(cfg, planilha, outlook)
    assert outlook.enviados == []
    assert planilha.aba("Status")[0] == ["Robô ligado?", "FALSE"]


def test_outlook_fecha_no_meio_nada_se_perde(cfg, planilha, outlook):
    # 2º e-mail falha e o Outlook não volta
    outlook.falhar_envios = {2}
    outlook.outlook_morre_apos_falha = True
    assert _rodar(cfg, planilha, outlook) == 1
    assert len(outlook.enviados) == 1
    marcadas = _coluna_enviado(planilha, ESTRELA) + _coluna_enviado(planilha, ARACAJU) + _coluna_enviado(planilha, BARRA)
    assert marcadas.count("TRUE") == 1 + len(outlook.enviados[0].solicitacoes)  # só as do e-mail que saiu (+ a que já era TRUE)

    # Outlook volta; próxima execução 15 min depois
    outlook.falhar_envios, outlook.outlook_morre_apos_falha = set(), False
    assert _rodar(cfg, planilha, outlook, agora=AGORA + datetime.timedelta(minutes=15)) == 0
    chaves = outlook.solicitacoes_enviadas()
    assert len(chaves) == 4 and len(set(chaves)) == 4   # todas foram, nenhuma duas vezes
    assert set(_coluna_enviado(planilha, ESTRELA) + _coluna_enviado(planilha, ARACAJU)) == {"TRUE"}


def test_enviou_mas_google_caiu_na_hora_de_marcar(cfg, planilha, outlook, pastas_temporarias):
    planilha.falhas_escrita = 1  # a marcação TRUE falha
    assert _rodar(cfg, planilha, outlook) == 1
    assert "FALSE" in _coluna_enviado(planilha, ARACAJU)
    assert os.path.exists(pastas_temporarias / "estado" / "envios_pendentes.json")

    # Próxima execução: acha os e-mails em Itens Enviados e só marca — NÃO reenvia
    assert _rodar(cfg, planilha, outlook) == 0
    assert len(outlook.enviados) == 2
    assert _coluna_enviado(planilha, ARACAJU) == ["TRUE"]


def test_email_preso_na_caixa_de_saida_nao_marca_nem_reenvia(cfg, planilha, outlook):
    outlook.prender_na_saida = True
    assert _rodar(cfg, planilha, outlook) == 1
    assert _coluna_enviado(planilha, ARACAJU) == ["FALSE"]

    _rodar(cfg, planilha, outlook, agora=AGORA + datetime.timedelta(hours=2))
    assert len(outlook.caixa_saida) == 2   # não mandou de novo
    assert _coluna_enviado(planilha, ARACAJU) == ["FALSE"]

    # Outlook finalmente manda
    outlook.enviados, outlook.caixa_saida = outlook.caixa_saida, []
    outlook.prender_na_saida = False
    assert _rodar(cfg, planilha, outlook, agora=AGORA + datetime.timedelta(hours=3)) == 0
    assert _coluna_enviado(planilha, ARACAJU) == ["TRUE"]
    assert len(outlook.enviados) == 2


def test_hotel_novo_na_aba_hoteis(cfg, planilha, outlook):
    # a aba de respostas do JERI aparece na planilha; o hotel já está no Cadastro_Hoteis (agente Bernardo)
    planilha.planilhas[CENTRAL]["Solicitação Nota Fiscal (Jeri) (respostas)"] = [CABECALHO_HOTEL, linha_hotel(9, "Jeri")]
    _rodar(cfg, planilha, outlook)
    op4 = [e for e in outlook.enviados if e.operador == "notafiscal4@andradehoteis.com.br"]
    assert len(op4) == 1 and op4[0].solicitacoes[0].hotel.nome == "JERI"


def test_aba_com_erro_e_pulada_e_as_outras_seguem(cfg, planilha, outlook):
    planilha.abas_com_erro.add(ARACAJU)
    planilha.planilhas[CENTRAL][BARRA] = [[c for c in CABECALHO_HOTEL if c != "Enviado"], linha_hotel(5)[:-1]]
    assert _rodar(cfg, planilha, outlook) == 0
    hoteis_enviados = {s.hotel.aba for e in outlook.enviados for s in e.solicitacoes}
    assert hoteis_enviados == {ESTRELA}   # Aracaju (erro) e Barra (sem coluna Enviado) pulados
    resumo = dict((l[0], l[1]) for l in planilha.aba("Status"))["Resumo da última execução"]
    assert "Aracaju" in resumo and "Barra" in resumo


def test_modo_teste_nao_marca(cfg, planilha, outlook):
    cfg["modo"] = "TESTE"
    _rodar(cfg, planilha, outlook)
    assert {e.destinatario for e in outlook.enviados} == {"teste@x.com"}
    assert _coluna_enviado(planilha, ARACAJU) == ["FALSE"]
    assert len(planilha.aba("Registros", "REGISTROS")) == 1


def test_modo_simulacao_so_gera_arquivo(cfg, planilha, outlook, pastas_temporarias):
    cfg["modo"] = "SIMULACAO"
    escritas_antes = planilha.escritas
    _rodar(cfg, planilha, outlook)
    assert outlook.enviados == [] and outlook.conexoes == 0
    assert planilha.escritas == escritas_antes
    assert len(os.listdir(pastas_temporarias / "simulacao")) == 2


def test_200_solicitacoes_de_uma_vez(cfg, planilha, outlook):
    cfg["limite_solicitacoes_por_email"] = 40
    for aba in (ESTRELA, ARACAJU, BARRA):
        planilha.planilhas[CENTRAL][aba] = [CABECALHO_HOTEL]
    for n in range(200):
        aba = (ESTRELA, ARACAJU, BARRA)[n % 3]
        planilha.aba(aba).append(linha_hotel(n, aba))
    assert _rodar(cfg, planilha, outlook) == 0
    chaves = outlook.solicitacoes_enviadas()
    assert len(chaves) == 200 and len(set(chaves)) == 200
    assert all(len(e.solicitacoes) <= 40 for e in outlook.enviados)
    for aba in (ESTRELA, ARACAJU, BARRA):
        assert set(_coluna_enviado(planilha, aba)) == {"TRUE"}


def test_marca_a_linha_certa_mesmo_se_alguem_ordenar_a_planilha(cfg, planilha):
    hoteis, _ = ler_hoteis(planilha, cfg)
    pendentes, _ = ler_pendentes(planilha, cfg, hoteis)
    alvo = [s for s in pendentes if s.hotel.aba == ESTRELA and s.email_hospede == "hospede1@x.com"]

    # alguém inverte a ordem das linhas entre a leitura e a marcação
    aba = planilha.aba(ESTRELA)
    aba[1:] = list(reversed(aba[1:]))
    marcar_enviados(planilha, cfg, alvo)

    enviado = CABECALHO_HOTEL.index("Enviado")
    por_email = {l[1]: l[enviado] for l in aba[1:]}
    assert por_email == {"hospede1@x.com": "TRUE", "hospede2@x.com": "TRUE", "hospede3@x.com": ""}
