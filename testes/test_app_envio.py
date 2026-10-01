import logging
import sys
import time
import types

import app_envio


def _esperar(envio, segundos=5):
    limite = time.time() + segundos
    while envio.situacao()["rodando"] and time.time() < limite:
        time.sleep(0.02)
    return envio.situacao()


def _robo_falso(monkeypatch, codigo=0, falhar=False):
    def rodar(codigo_se_ocupado=0, origem=None, quem=None, selecao=None):
        log = logging.getLogger("main")
        log.info("📋 3 solicitação(ões) pendente(s) lida(s).")
        log.info("📤 Enviando NF-ABC -> hotel@x.com")
        log.warning("⚠️ aviso no meio")
        if falhar:
            raise RuntimeError("Outlook fechado")
        log.info("✅ 3 e-mail(s) enviado(s), 3 solicitação(ões) marcada(s) TRUE")
        return codigo
    monkeypatch.setitem(sys.modules, "main", types.SimpleNamespace(rodar=rodar, OCUPADO=3))


def test_envio_local_captura_o_log_e_o_resumo(monkeypatch):
    _robo_falso(monkeypatch)
    terminou = []
    e = app_envio.Envio(ao_terminar=lambda: terminou.append(1))
    assert e.iniciar_local("Clara") is True
    s = _esperar(e)
    assert s["codigo"] == 0 and s["resumo"].startswith("3 e-mail(s) enviado(s)")
    assert [l["texto"][0] for l in s["linhas"]][:2] == ["📋", "📤"]
    assert any(l["nivel"] == "WARNING" for l in s["linhas"])
    assert terminou == [1]


def test_log_de_outra_thread_nao_entra(monkeypatch):
    _robo_falso(monkeypatch)
    e = app_envio.Envio()
    e.iniciar_local("Clara")
    logging.getLogger("main").info("linha de outra thread")
    s = _esperar(e)
    assert all("outra thread" not in l["texto"] for l in s["linhas"])


def test_robo_ocupado_e_erro(monkeypatch):
    _robo_falso(monkeypatch, codigo=3)
    e = app_envio.Envio()
    e.iniciar_local("Clara")
    assert "Já tinha um envio" in _esperar(e)["resumo"]
    _robo_falso(monkeypatch, falhar=True)
    e2 = app_envio.Envio()
    e2.iniciar_local("Clara")
    s = _esperar(e2)
    assert s["codigo"] == 1 and "Outlook fechado" in s["resumo"]


def test_nao_inicia_dois_ao_mesmo_tempo(monkeypatch):
    def lento(**_):
        time.sleep(0.3)
        return 0
    monkeypatch.setitem(sys.modules, "main", types.SimpleNamespace(rodar=lento, OCUPADO=3))
    e = app_envio.Envio()
    assert e.iniciar_local("Clara") is True
    assert e.iniciar_local("João") is False
    _esperar(e)


def test_envio_remoto_le_o_andamento_da_aba_status():
    e = app_envio.Envio()
    e.iniciar_remoto()
    s = e.situacao(lambda: {"Comando": "EM ANDAMENTO", "Andamento do envio (ao vivo)": "10:00:01  📋 2 pendentes\n10:00:02  📤 Enviando"})
    assert s["rodando"] and [l["texto"] for l in s["linhas"]] == ["📋 2 pendentes", "📤 Enviando"]
    e.estado["pedido_em"] = 0   # passou da espera inicial
    s = e.situacao(lambda: {"Comando": "", "Resposta do robô": "✅ 2 e-mail(s) enviado(s)"})
    assert not s["rodando"] and s["resumo"].startswith("✅")
    assert e.situacao(lambda: {})["codigo"] == 0
