import datetime

import app_dados as d
from app_servidor import Estado
from conftest import CENTRAL, ESTRELA

T = datetime.datetime(2026, 10, 1, 9, 0, 0)
CAB = [d.CABECALHO_TRATAMENTO]


def ev(agente, acao, valor="", aba="A", carimbo="1/10/2026 08:00:00", email="h@x.com"):
    return d.evento(T, agente, "PC", aba, carimbo, email, acao, valor)


def est(linhas, aba="A", carimbo="1/10/2026 08:00:00", email="h@x.com"):
    return d.dobrar_eventos(CAB + linhas)[d.chave(aba, carimbo, email)]


def test_primeiro_assumir_vence_mesmo_com_dois_seguidos():
    e = est([ev("Clara", d.ASSUMIR), ev("João", d.ASSUMIR)])
    assert e["dono"] == "Clara"


def test_so_o_dono_libera_ou_forcando():
    assert est([ev("Clara", d.ASSUMIR), ev("João", d.LIBERAR)])["dono"] == "Clara"
    assert est([ev("Clara", d.ASSUMIR), ev("Clara", d.LIBERAR)])["dono"] == ""
    assert est([ev("Clara", d.ASSUMIR), ev("João", d.LIBERAR, "forcar")])["dono"] == ""


def test_depois_de_liberar_outro_pode_assumir():
    e = est([ev("Clara", d.ASSUMIR), ev("Clara", d.LIBERAR), ev("João", d.ASSUMIR)])
    assert e["dono"] == "João"


def test_nf_sem_repetir_e_desfazer():
    e = est([ev("Clara", d.NF, "643"), ev("João", d.NF, "643"), ev("Clara", d.NF, "644"), ev("Clara", d.DESFAZER_NF, "643")])
    assert e["nfs"] == ["644"]


def test_chave_ignora_maiusculas_do_email():
    linhas = CAB + [ev("Clara", d.ASSUMIR, email="H@X.com")]
    assert d.chave("A", "1/10/2026 08:00:00", "h@x.com") in d.dobrar_eventos(linhas)


def test_linha_com_acao_desconhecida_e_ignorada():
    assert d.dobrar_eventos(CAB + [["x", "Clara", "PC", "A", "c", "e", "APAGAR_TUDO", ""]]) == {}


def test_situacao():
    sol = {"enviado": True, "partes": 1}
    vazio = d.estado_inicial()
    assert d.situacao({**sol, "enviado": False}, vazio) == d.AGUARDANDO_ENVIO
    assert d.situacao(sol, vazio) == d.NA_FILA
    assert d.situacao(sol, {**vazio, "dono": "Clara"}) == d.EM_TRATAMENTO
    assert d.situacao(sol, {**vazio, "tratativas": [{"texto": "x"}]}) == d.EM_TRATATIVA
    assert d.situacao(sol, {**vazio, "nfs": ["1"]}) == d.CONCLUIDA
    assert d.situacao({**sol, "partes": 2}, {**vazio, "nfs": ["1"]}) == d.NF_PARCIAL
    assert d.situacao(sol, {**vazio, "dividida": True, "nfs": ["1"]}) == d.NF_PARCIAL
    assert d.situacao(sol, vazio, nfs_conferente=["9"]) == d.CONCLUIDA


def test_nfs_do_controle_ignora_as_a_conferir():
    reg = {"solicitacoes": {"r1": {"aba": "A", "carimbo": "c", "nfs": {"10": {}, "11": {"conferir": True}}}}}
    assert d.nfs_do_controle(reg) == {("A", "c"): ["10"]}


def test_ler_solicitacoes_da_central(cfg, planilha):
    sols = d.ler_solicitacoes(ESTRELA, "ESTRELA CENTRO", planilha.aba(ESTRELA), cfg)
    assert [s["linha"] for s in sols] == [2, 3, 4]
    assert [s["enviado"] for s in sols] == [False, True, False]
    assert sols[0]["nome"] == "Hóspede Número 1 Silva" and sols[0]["data"] == "2026-09-02"
    assert all(c[0] != "Enviado" for c in sols[0]["campos"])


def test_estado_le_a_central_e_cria_a_aba_tratamento(cfg, planilha):
    e = Estado(planilha, cfg)
    e.atualizar()
    assert e.erro == ""
    assert planilha.aba(d.ABA_TRATAMENTO) == [d.CABECALHO_TRATAMENTO]
    assert len(e.solicitacoes) == 5
    assert e.resumo_status()["ligado"] is True


def test_assumir_grava_na_planilha_e_o_segundo_e_recusado(cfg, planilha):
    pc1, pc2 = Estado(planilha, cfg), Estado(planilha, cfg)
    pc1.atualizar(), pc2.atualizar()
    k = pc1.solicitacoes[0]["chave"]
    assert pc1.registrar("Clara", "PC1", k, d.ASSUMIR) == {"ok": True}
    r = pc2.registrar("João", "PC2", k, d.ASSUMIR)
    assert r["ok"] is False and "Clara" in r["motivo"]
    assert len(planilha.aba(d.ABA_TRATAMENTO)) == 2


def test_corrida_quem_grava_primeiro_ganha(cfg, planilha):
    """Os dois leram 'livre'; a planilha serializa as gravações e o segundo descobre que perdeu."""
    pc1, pc2 = Estado(planilha, cfg), Estado(planilha, cfg)
    pc1.atualizar(), pc2.atualizar()
    k = pc1.solicitacoes[0]["chave"]
    original = pc2.reler_tratamento
    pc2.reler_tratamento = lambda: None          # pc2 não vê a gravação do pc1 antes de gravar
    pc1.registrar("Clara", "PC1", k, d.ASSUMIR)
    pc2.reler_tratamento = lambda: (setattr(pc2, "reler_tratamento", original), original())[1]
    r = pc2.registrar("João", "PC2", k, d.ASSUMIR)
    assert r["ok"] is False and "Clara" in r["motivo"]
    assert d.quem_ganhou(pc2.estados, k) == "Clara"


def test_acao_invalida_e_chave_inexistente(cfg, planilha):
    e = Estado(planilha, cfg)
    e.atualizar()
    import pytest
    with pytest.raises(KeyError):
        e.registrar("Clara", "PC", "nao existe", d.ASSUMIR)
    with pytest.raises(ValueError):
        e.registrar("Clara", "PC", e.solicitacoes[0]["chave"], "APAGAR")


def test_fila_mostra_nf_e_dono(cfg, planilha):
    e = Estado(planilha, cfg)
    e.atualizar()
    k = e.solicitacoes[0]["chave"]
    e.registrar("Clara", "PC", k, d.ASSUMIR)
    e.registrar("Clara", "PC", k, d.NF, "700")
    item = next(s for s in e.fila(0) if s["chave"] == k)
    assert item["dono"] == "Clara" and item["nfs"] == ["700"] and item["situacao"] == d.CONCLUIDA


def test_cache_em_disco_reabre_com_os_dados(cfg, planilha, tmp_path, monkeypatch):
    import app_servidor
    monkeypatch.setattr(app_servidor, "CAMINHO_CACHE", tmp_path / "painel_cache.pkl")
    e = Estado(planilha, cfg)
    e.atualizar()
    e.registrar("Clara", "PC", e.solicitacoes[0]["chave"], d.ASSUMIR)
    e.salvar_cache(forcar=True)
    novo = Estado(planilha, cfg)            # PC reiniciado: nada lido ainda
    assert novo.carregar_cache() is True
    assert len(novo.solicitacoes) == 5 and novo.atualizado_em == e.atualizado_em
    assert next(s for s in novo.fila(0) if s["chave"] == e.solicitacoes[0]["chave"])["dono"] == "Clara"


def test_cache_corrompido_e_ignorado(cfg, planilha, tmp_path, monkeypatch):
    import app_servidor
    caminho = tmp_path / "painel_cache.pkl"
    caminho.write_bytes(b"lixo")
    monkeypatch.setattr(app_servidor, "CAMINHO_CACHE", caminho)
    assert Estado(planilha, cfg).carregar_cache() is False


def test_falha_de_leitura_nao_derruba(cfg, planilha):
    e = Estado(planilha, cfg)
    planilha.listar_abas = lambda _id: (_ for _ in ()).throw(RuntimeError("503"))
    e.atualizar()
    assert "503" in e.erro


def test_tema_e_operador_ficam_juntos_nas_preferencias_do_pc(tmp_path, monkeypatch):
    import app_servidor
    monkeypatch.setattr(app_servidor, "CAMINHO_PREFS", tmp_path / "app.json")
    app_servidor.salvar_pref("agente", "Clara")
    app_servidor.salvar_pref("tema", "dark")
    assert app_servidor.ler_prefs() == {"agente": "Clara", "tema": "dark"}   # trocar o tema não apaga o operador
    assert app_servidor.nome_do_agente() == "Clara"
