"""Log de Envios, válvula de escape (ja_enviadas.json) e Envio Separado."""
import csv

from conftest import ARACAJU, CABECALHO_HOTEL, ESTRELA, Relogio
from historico import (ABA_LOG, ATENCAO, CABECALHO_LOG, ERRO, NADA, ORIGEM_AGENDADO, ORIGEM_CLAUDIO,
                       ORIGEM_SEPARADO, SUCESSO, Execucao, _faixas, texto_simples)
from main import executar, ler_selecao

ENV = CABECALHO_HOTEL.index("Enviado")


def _rodar(cfg, planilha, outlook, origem=ORIGEM_CLAUDIO, selecao=None, pasta=None):
    log = Execucao(origem, "joao@andradehoteis.com.br", cfg["modo"])
    r = Relogio()
    codigo = executar(cfg, planilha, outlook, esperar=r.esperar, relogio=r.agora, log_exec=log, selecao=selecao)
    log.gravar(planilha, cfg, pasta)
    return codigo, log


def _log(planilha):
    tabela = planilha.aba(ABA_LOG)
    assert tabela[0] == CABECALHO_LOG
    return [dict(zip(CABECALHO_LOG, l)) for l in tabela[1:]]


def test_log_de_um_envio_normal(cfg, planilha, outlook, tmp_path):
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    linhas = _log(planilha)
    # uma linha por hotel: ESTRELA CENTRO + BARRA (João) e ARACAJU (Clara)
    assert sorted(l["Hotel"] for l in linhas) == ["ARACAJU", "BARRA", "ESTRELA CENTRO"]
    estrela = next(l for l in linhas if l["Hotel"] == "ESTRELA CENTRO")
    assert estrela["Resultado"] == SUCESSO
    assert estrela["Quem pediu"] == "joao@andradehoteis.com.br" and estrela["Como foi pedido"] == ORIGEM_CLAUDIO
    assert estrela["Enviado para"] == "notafiscal1@andradehoteis.com.br" and estrela["Agente"] == "João"
    assert estrela["Qtd. de solicitações"] == 2 and estrela["Linhas da planilha"] == "2, 4"
    assert estrela["E-mails desta execução"] == "2 enviado(s) de 2"
    assert estrela["Modo"] == "Valendo" and estrela["Código do e-mail (procure no Outlook)"].startswith("NF-")
    assert not any("{" in str(v) for l in linhas for v in l.values())  # nada de JSON pra quem lê
    with open(tmp_path / "Historico_de_Envios.csv", encoding="utf-8-sig") as f:   # cópia no computador
        assert len(list(csv.reader(f, delimiter=";"))) == 1 + 3


def test_mais_recente_fica_no_topo(cfg, planilha, outlook, tmp_path):
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    assert _log(planilha)[0]["Resultado"] == NADA


def test_agendado_sem_nada_pra_enviar_nao_enche_o_log(cfg, planilha, outlook, tmp_path):
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    antes = len(_log(planilha))
    _rodar(cfg, planilha, outlook, origem=ORIGEM_AGENDADO, pasta=tmp_path)
    assert len(_log(planilha)) == antes


def test_valvula_de_escape_nao_reenvia_quando_o_true_some(cfg, planilha, outlook, tmp_path):
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    assert len(outlook.enviados) == 2
    # alguém apaga o TRUE da ARACAJU (ou o Google falhou) — mas o robô já tinha enviado
    planilha.aba(ARACAJU)[1][ENV] = "FALSE"
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    assert len(outlook.enviados) == 2                                  # NÃO reenviou
    assert planilha.aba(ARACAJU)[1][ENV] == "TRUE"                     # só remarcou
    topo = _log(planilha)[0]
    assert topo["Resultado"] == ATENCAO and topo["Hotel"] == "ARACAJU" and "Não enviei de novo" in topo["O que aconteceu"]


def test_envio_separado_manda_so_o_escolhido(cfg, planilha, outlook, tmp_path):
    selecao = ler_selecao(f"{ESTRELA} | 4")
    _rodar(cfg, planilha, outlook, origem=ORIGEM_SEPARADO, selecao=selecao, pasta=tmp_path)
    [email] = outlook.enviados
    assert [s.linha for s in email.solicitacoes] == [4]
    # linhas 2, 3, 4: a 2 continua pendente, a 3 já era TRUE, a 4 (escolhida) virou TRUE
    assert [l[ENV] for l in planilha.aba(ESTRELA)[1:]] == ["FALSE", "TRUE", "TRUE"]
    assert planilha.aba(ARACAJU)[1][ENV] == "FALSE"                            # outro hotel nem foi tocado
    assert _log(planilha)[0]["Como foi pedido"] == ORIGEM_SEPARADO


def test_envio_separado_ignora_o_filtro_de_teste(cfg, planilha, outlook, tmp_path):
    cfg["somente_hoteis"] = ["BARRA"]
    _rodar(cfg, planilha, outlook, origem=ORIGEM_SEPARADO, selecao=ler_selecao(f"{ARACAJU} | 2"), pasta=tmp_path)
    assert [s.hotel.nome for e in outlook.enviados for s in e.solicitacoes] == ["ARACAJU"]


def test_envio_separado_reenvia_linha_com_true_so_se_pedir(cfg, planilha, outlook, tmp_path):
    _rodar(cfg, planilha, outlook, origem=ORIGEM_SEPARADO, selecao=ler_selecao(f"{ESTRELA} | 3"), pasta=tmp_path)
    assert outlook.enviados == []                                       # linha 3 já tinha TRUE
    assert "reenviar" in _log(planilha)[0]["O que aconteceu"]
    _rodar(cfg, planilha, outlook, origem=ORIGEM_SEPARADO, selecao=ler_selecao(f"{ESTRELA} | 3 | reenviar"),
           pasta=tmp_path)
    assert [s.linha for e in outlook.enviados for s in e.solicitacoes] == [3]
    assert "Reenviado a pedido" in _log(planilha)[0]["O que aconteceu"]


def test_falha_do_outlook_aparece_explicada(cfg, planilha, outlook, tmp_path):
    outlook.falhar_envios, outlook.outlook_morre_apos_falha = {1}, True
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    linhas = _log(planilha)
    assert all(l["Resultado"] == ERRO for l in linhas)
    assert all("Não foi enviado" in l["O que aconteceu"] for l in linhas)
    assert linhas[0]["E-mails desta execução"] == "0 enviado(s) de 2"


def test_robo_desligado_fica_no_log_quando_alguem_pede(cfg, planilha, outlook, tmp_path):
    planilha.aba("Status")[0][1] = "FALSE"
    _rodar(cfg, planilha, outlook, pasta=tmp_path)
    assert "DESLIGADO" in _log(planilha)[0]["O que aconteceu"]


def test_frases_simples():
    assert "Outlook" in texto_simples(RuntimeError("Outlook fechado"))
    assert "permissão" in texto_simples(PermissionError(""))
    assert _faixas([131, 132, 133, 140]) == "131 a 133, 140"
    assert ler_selecao("aba X | 12, 14 | reenviar") == {"aba": "aba X", "linhas": {12, 14}, "reenviar": True}
    assert ler_selecao("") is None and ler_selecao("aba X | ") is None
