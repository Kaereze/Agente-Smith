"""Guardião do Outlook (13/10/2026): Outlook sem janela (aberto pelo COM) não baixa e-mail POP3 — o caso do PC do Cristian."""
import datetime

import outlook_vivo as ov
import saude


def _sem_cache(monkeypatch):
    ov._cache.update(em=-1e9, estado=None)
    ov._falhas.update(n=0, pausa_ate=0.0)


def test_estado_distingue_fechado_sem_janela_e_aberto(monkeypatch):
    _sem_cache(monkeypatch)
    monkeypatch.setattr(ov, "_pids_outlook", lambda: set())
    assert ov.estado(cache_segundos=0) == ov.FECHADO
    monkeypatch.setattr(ov, "_pids_outlook", lambda: {8288})
    monkeypatch.setattr(ov, "_pids_com_janela", lambda pids: set())
    assert ov.estado(cache_segundos=0) == ov.SEM_JANELA          # o OUTLOOK.EXE "-Embedding" do Cristian
    monkeypatch.setattr(ov, "_pids_com_janela", lambda pids: {8288})
    assert ov.estado(cache_segundos=0) == ov.ABERTO


def test_garantir_abre_o_outlook_normal_quando_esta_sem_janela(monkeypatch):
    _sem_cache(monkeypatch)
    monkeypatch.setattr(ov, "_em_teste", lambda: False)
    monkeypatch.setattr(ov.time, "sleep", lambda s: None)
    estados = iter([ov.SEM_JANELA, ov.ABERTO])
    monkeypatch.setattr(ov, "estado", lambda cache_segundos=20: next(estados))
    abriu = []
    monkeypatch.setattr(ov, "_abrir", lambda: abriu.append(1))
    assert ov.garantir("teste") is True
    assert abriu == [1]


def test_garantir_para_de_insistir_depois_de_3_falhas(monkeypatch):
    _sem_cache(monkeypatch)
    monkeypatch.setattr(ov, "_em_teste", lambda: False)
    monkeypatch.setattr(ov.time, "sleep", lambda s: None)
    monkeypatch.setattr(ov, "estado", lambda cache_segundos=20: ov.FECHADO)
    monkeypatch.setattr(ov, "_esperar_aberto", lambda s: False)
    abriu = []
    monkeypatch.setattr(ov, "_abrir", lambda: abriu.append(1))
    for _ in range(5):
        assert ov.garantir() is False
    assert len(abriu) == 3                                       # 3 tentativas, depois pausa de 30 min


def test_aplicativo_nao_cria_outlook_escondido_se_nao_abriu(monkeypatch):
    monkeypatch.setattr(ov, "garantir", lambda motivo="": False)
    try:
        ov.aplicativo("teste")
        assert False, "devia avisar em vez de chamar o COM"
    except RuntimeError as e:
        assert "sem janela" in str(e)


def _pc(pc, agente, outlook="aberto", rec=""):
    return {"pc": pc, "agente": agente, "online": True, "outlook": outlook, "versao": "v1", "saude": {"rec": rec}}


def test_saude_avisa_outlook_sem_janela():
    textos = [p["texto"] for p in saude.problemas([_pc("P1", "João"), _pc("P2", "Cristian", outlook="sem janela")])]
    assert any("Cristian" in t and "sem janela" in t for t in textos)


def test_saude_avisa_quando_nenhum_email_novo_chega():
    agora = datetime.datetime(2026, 10, 13, 9, 0)
    pcs = [_pc("P1", "João", rec="2026-10-13T08:40:00"), _pc("P2", "Clara", rec="2026-10-13T07:30:00"),
           _pc("P3", "Cristian", rec="2026-10-09T10:23:00")]
    textos = [p["texto"] for p in saude.problemas(pcs, agora)]
    assert any("Cristian" in t and "09/10 10:23" in t for t in textos)
    assert not any("Clara" in t and "Nenhum e-mail" in t for t in textos)


def test_saude_nao_alarma_de_madrugada_nem_com_um_pc_so():
    madrugada = datetime.datetime(2026, 10, 13, 3, 0)
    pcs = [_pc("P1", "João", rec="2026-10-13T02:40:00"), _pc("P3", "Cristian", rec="2026-10-12T10:00:00")]
    assert not any("Nenhum e-mail" in p["texto"] for p in saude.problemas(pcs, madrugada))
    so_um = [_pc("P3", "Cristian", rec="2026-10-09T10:23:00")]
    assert not any("Nenhum e-mail" in p["texto"] for p in saude.problemas(so_um, datetime.datetime(2026, 10, 13, 9, 0)))


def test_coluna_de_saude_leva_o_ultimo_recebido():
    texto = saude.coluna(0, recebido="2026-10-13T08:07:20")
    assert saude.ler_coluna(texto)["rec"] == "2026-10-13T08:07:20"


def test_atualizador_avanca_sem_git_pull(monkeypatch):
    # 13/10/2026: "git pull" falhava no PC do Bernardo (FETCH_HEAD duplicado); agora fetch + merge --ff-only origin/<ramo>
    import atualizador
    chamadas = []

    def git(*args, timeout=60):
        chamadas.append(args)
        return "main" if args[:2] == ("rev-parse", "--abbrev-ref") else ""

    monkeypatch.setattr(atualizador, "_git", git)
    monkeypatch.setattr(atualizador, "versao", lambda: "abc 13/10")
    monkeypatch.setattr(atualizador, "pedir_reinicio", lambda: "reinício pedido", raising=False)
    monkeypatch.setattr(atualizador.subprocess, "run", lambda *a, **k: None)   # sem pip install de verdade
    atualizador.atualizar()
    assert ("merge", "--ff-only", "origin/main") in chamadas
    assert not any(a and a[0] == "pull" for a in chamadas)
