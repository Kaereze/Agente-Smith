"""Painel leve e espelho (08/10/2026): o que o Painel baixa a cada volta, a Tratamento só pelo fim, faxina detectada,
correio dos 4 PCs junto (respondido/excluído some, lido vale pra equipe) e solicitação resolvida some em 24 h."""
import datetime

import app_dados as d
import app_servidor
import espelho_emails as ee
from app_servidor import Estado
from conftest import CENTRAL, ESTRELA


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _espiar(planilha):
    pedidos = []
    original = planilha.ler_abas

    def ler(pid, nomes, faixas=None):
        pedidos.append((list(nomes), dict(faixas or {})))
        return original(pid, nomes, faixas)
    planilha.ler_abas = ler
    return pedidos


def _ev(agente, acao, valor, carimbo, email, quando=None):
    return d.evento(quando or d.agora(), agente, "PC", ESTRELA, carimbo, email, acao, valor)


def test_tratamento_vem_so_pelo_fim_e_abas_dos_hoteis_a_cada_2_min(cfg, planilha):
    rel = Relogio()
    e = Estado(planilha, cfg, relogio=rel)
    pedidos = _espiar(planilha)
    e.atualizar()
    assert ESTRELA in pedidos[-1][0] and pedidos[-1][1] == {}           # 1ª volta: tudo
    sol = e.solicitacoes[0]
    planilha.anexar_linhas(CENTRAL, d.ABA_TRATAMENTO, [_ev("Clara", d.NF, "700", sol["carimbo"], sol["email"])])
    rel.t += 15
    e.atualizar()
    nomes, faixas = pedidos[-1]
    assert ESTRELA not in nomes                                          # hotéis: só daqui a 2 min
    assert faixas == {d.ABA_TRATAMENTO: "A1:H"}                          # do fim conhecido em diante
    assert e.estados[sol["chave"]]["nfs"] == ["700"]                     # a linha nova entrou
    rel.t += app_servidor.HOTEIS_SEGUNDOS
    e.atualizar()
    assert ESTRELA in pedidos[-1][0] and pedidos[-1][1] == {d.ABA_TRATAMENTO: "A2:H"}


def test_faxina_por_baixo_faz_reler_inteira_e_leitura_falha_nao_apaga_nada(cfg, planilha):
    rel = Relogio()
    e = Estado(planilha, cfg, relogio=rel)
    e.atualizar()
    s1, s2 = e.solicitacoes[0], e.solicitacoes[1]
    planilha.anexar_linhas(CENTRAL, d.ABA_TRATAMENTO, [_ev("Clara", d.OBS, "x", s1["carimbo"], s1["email"]),
                                                       _ev("Clara", d.NF, "10", s1["carimbo"], s1["email"]),
                                                       _ev("Clara", d.NF, "20", s2["carimbo"], s2["email"])])
    rel.t += 15
    e.atualizar()
    assert e.estados[s2["chave"]]["nfs"] == ["20"]
    planilha.apagar_linhas(CENTRAL, d.ABA_TRATAMENTO, 2, 3)              # faxina apagou a OBS velha
    rel.t += 15
    e.atualizar()
    assert len(e.trat_linhas) == 3 and e.estados[s1["chave"]]["nfs"] == ["10"] and not e.estados[s1["chave"]]["obs"]
    planilha.abas_com_erro.add(d.ABA_TRATAMENTO)                         # Google falhou só nessa aba
    rel.t += app_servidor.TRATAMENTO_COMPLETO_SEGUNDOS
    e.atualizar()
    assert e.estados[s2["chave"]]["nfs"] == ["20"]                       # não virou "tudo pendente"


def _correio(planilha, pc, itens, enviados=None, agora=None):
    agora = agora or datetime.datetime.now()
    planilha.substituir_aba(CENTRAL, ee.nome_aba(pc), ee.linhas_da_aba(itens, enviados or {}, pc, agora))


def _item(i, de, quando, caixa="nf@luxor.com", hotel="LUXOR", classes=()):
    return {"id": i, "pasta": "entrada", "caixa": caixa, "hotel": hotel, "de": de, "nome": de.split("@")[0].title(),
            "assunto": "Nota fiscal", "quando": quando.isoformat(timespec="seconds"), "anexos": [], "texto": "Oi",
            "classes": list(classes)}


def test_correio_dos_4_pcs_uma_linha_por_hospede_e_respondido_por_outro_pc_some(cfg, planilha):
    agora = datetime.datetime.now().replace(microsecond=0)
    h = datetime.timedelta(hours=1)
    _correio(planilha, "PC-JOAO", {"a1": _item("a1", "ana@gmail.com", agora - 2 * h),
                                   "a2": _item("a2", "ana@gmail.com", agora - h),
                                   "b1": _item("b1", "bia@gmail.com", agora - 9 * 24 * h),             # +7 dias
                                   "c1": _item("c1", "caio@gmail.com", agora - h, classes=["corrigir"])})
    # Bia mandou pra caixa do João; quem respondeu foi uma caixa do PC da Clara
    _correio(planilha, "PC-CLARA", {"d1": _item("d1", "duda@gmail.com", agora - h, "nf@aracaju.com", "ARACAJU")},
             enviados={"caio@gmail.com": agora - 30 * datetime.timedelta(minutes=1)})
    e = Estado(planilha, cfg)
    e.atualizar()
    c = e.lista_correio()
    por_de = {x["de"]: x for x in c["conversas"]}
    assert set(por_de) == {"ana@gmail.com", "bia@gmail.com", "duda@gmail.com"}   # Caio: respondido pelo outro PC
    assert por_de["ana@gmail.com"]["total"] == 2 and por_de["ana@gmail.com"]["nao_lidos"] == 2
    assert por_de["ana@gmail.com"]["ultimo"]["id"] == "a2"
    assert por_de["bia@gmail.com"]["urgente"] and not por_de["ana@gmail.com"]["urgente"]
    # contagem = a caixa inteira, igual ao Outlook (14/10/2026): o Caio respondido segue na lista, marcado
    assert c["contagem"] == {"entrada_nao_lidos": 5, "entrada": 5, "urgencia": 1, "urgencia_nao_lidos": 1}
    assert any(e["de"] == "caio@gmail.com" and e["respondido"] and not e["urgente"] for e in c["emails"])


def test_lido_vale_pra_equipe_e_vai_numa_escrita_so(cfg, planilha):
    agora = datetime.datetime.now().replace(microsecond=0)
    _correio(planilha, "PC-JOAO", {"a1": _item("a1", "ana@gmail.com", agora), "a2": _item("a2", "ana@gmail.com", agora)})
    pc1, pc2 = Estado(planilha, cfg), Estado(planilha, cfg)
    pc1.atualizar(), pc2.atualizar()
    escritas = []
    original = planilha.anexar_linhas
    planilha.anexar_linhas = lambda pid, aba, linhas: (escritas.append(aba), original(pid, aba, linhas))
    pc1.evento_correio(["a1", "a2"], "LIDO", "Clara")
    assert pc1.lista_correio()["conversas"][0]["nao_lidos"] == 0          # na hora, na tela de quem clicou
    assert escritas == []                                                   # ainda não gravou
    pc1.atualizar()
    assert escritas == [ee.ABA_EVENTOS]                                     # 2 e-mails, 1 escrita
    pc2.atualizar()
    ana = pc2.lista_correio()["conversas"][0]
    assert ana["nao_lidos"] == 0 and pc2.eventos_correio["a1"]["lido_por"] == "Clara"


def test_solicitacao_resolvida_fica_24h_e_some_da_lista(cfg, planilha):
    e = Estado(planilha, cfg)
    e.atualizar()
    s_hoje, s_velha = e.solicitacoes[0], e.solicitacoes[1]
    ontem = d.agora() - datetime.timedelta(hours=30)
    planilha.anexar_linhas(CENTRAL, d.ABA_TRATAMENTO, [
        _ev("Clara", d.NF, "1", s_hoje["carimbo"], s_hoje["email"]),
        _ev("Clara", d.OBS, f"E-mail com a NF 1 enviado para {s_hoje['email']} em {d.agora():%d/%m/%Y %H:%M}",
            s_hoje["carimbo"], s_hoje["email"]),
        _ev("Clara", d.NF, "2", s_velha["carimbo"], s_velha["email"], quando=ontem),
        _ev("Clara", d.OBS, f"E-mail com a NF 2 enviado para {s_velha['email']} em {ontem:%d/%m/%Y %H:%M}",
            s_velha["carimbo"], s_velha["email"], quando=ontem)])
    e.atualizar(completo=True)
    chaves = {s["chave"] for s in e.fila_da_tela(0)}
    assert s_hoje["chave"] in chaves and s_velha["chave"] not in chaves
    assert s_velha["chave"] in {s["chave"] for s in e.fila(0)}              # a Visão geral ainda conta
