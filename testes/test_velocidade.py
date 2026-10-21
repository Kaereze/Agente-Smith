"""Velocidade (usuário, 21/10/2026: "deixar tudo mais rápido"): novidade do robô relê na hora e NF do Dropbox na hora."""
import threading
import time
import types

import app_servidor
import conferente


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


def _estado_falso(olhados=None):
    e = types.SimpleNamespace(acordar=threading.Event())
    e.olhar_dropbox = lambda: (olhados.append(1) if olhados is not None else None)
    return e


def test_novidade_adianta_a_leitura_mas_espera_12_s_desde_a_ultima():
    rel, estado = Relogio(), _estado_falso()
    estado.acordar.set()
    inicio = rel.t
    assert app_servidor.esperar_proxima_volta(estado, [rel.t], 15, 60, rel, rel.dormir) == "novidade"
    assert rel.t - inicio == app_servidor.ACORDAR_MIN_SEGUNDOS        # nunca antes de 12 s (cota do Google)


def test_sem_novidade_relê_no_tempo_de_sempre():
    rel, olhados = Relogio(), []
    estado = _estado_falso(olhados)
    inicio = rel.t
    assert app_servidor.esperar_proxima_volta(estado, [rel.t], 15, 60, rel, rel.dormir) == "tempo"
    assert rel.t - inicio == 15 and len(olhados) == 15                # olha o Dropbox enquanto espera


def test_janela_fechada_nao_adianta_com_novidade():
    rel, estado = Relogio(), _estado_falso()
    estado.acordar.set()
    inicio = rel.t
    assert app_servidor.esperar_proxima_volta(estado, [-1e9], 15, 60, rel, rel.dormir) == "tempo"
    assert rel.t - inicio == 60


def test_erro_ao_olhar_o_dropbox_nao_derruba_o_laco():
    rel, estado = Relogio(), _estado_falso()
    estado.olhar_dropbox = lambda: 1 / 0
    assert app_servidor.esperar_proxima_volta(estado, [rel.t], 15, 60, rel, rel.dormir) == "tempo"


def _estado_rede(monkeypatch, enderecos):
    e = object.__new__(app_servidor.Estado)
    e.segredo = b"segredo-de-teste"
    e._enderecos_rede = lambda: dict(enderecos)
    anotados, perguntas = [], []
    e._anotar_rede = anotados.append
    monkeypatch.setattr(app_servidor.rede_local, "perguntar_a_todos",
                        lambda segredo, ends, acao, corpo, tempo=0: (perguntas.append((dict(ends), acao, corpo)),
                                                                     {pc: {"ok": True} for pc in ends})[1])
    return e, perguntas, anotados


def _esperar_threads():
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon and "_repassar_novidade" in str(getattr(t, "_target", "")):
            t.join(5)
    time.sleep(0.05)


def test_novidade_do_robo_acorda_e_repassa_uma_vez_aos_outros(monkeypatch):
    e, perguntas, anotados = _estado_rede(monkeypatch, {"PC-B": "10.0.0.2:8766", "PC-C": "10.0.0.3:8766"})
    assert e.rede_novidade({"o_que": "emails"}) == {"ok": True}
    _esperar_threads()
    assert e.acordar.is_set()
    assert perguntas == [({"PC-B": "10.0.0.2:8766", "PC-C": "10.0.0.3:8766"}, "novidade",
                          {"o_que": "emails", "repassado": True})]
    assert anotados and set(anotados[0]) == {"PC-B", "PC-C"}


def test_novidade_repassada_nao_e_repassada_de_novo(monkeypatch):
    e, perguntas, _ = _estado_rede(monkeypatch, {"PC-B": "10.0.0.2:8766"})
    e.rede_novidade({"o_que": "nf", "repassado": True})
    _esperar_threads()
    assert e.acordar.is_set() and perguntas == []                      # sem laço de avisos entre os PCs


def test_olhar_dropbox_refaz_as_nfs_so_quando_a_pasta_muda(monkeypatch):
    e = object.__new__(app_servidor.Estado)
    e.cfg, e.versao_tela, e.marca_dropbox, e.dropbox_olhado = {}, 0, None, -1e9
    marcas = iter([(1, 2), (1, 2), (1, 3)])
    feitos = []
    monkeypatch.setattr(app_servidor.envio_nf, "marca_das_pastas", lambda cfg: next(marcas))
    monkeypatch.setattr(app_servidor.envio_nf, "listar_notas_dropbox", lambda cfg, forcar=False: feitos.append(("lista", forcar)))
    e.atualizar_notas_emails = lambda forcar=False: feitos.append(("emails", forcar))
    assert e.olhar_dropbox() is False                                  # 1ª olhada: só memoriza
    assert e.olhar_dropbox() is False                                  # menos de 10 s depois: nem olha
    e.dropbox_olhado -= app_servidor.DROPBOX_OLHAR_SEGUNDOS
    assert e.olhar_dropbox() is False and not feitos                   # pasta igual
    e.dropbox_olhado -= app_servidor.DROPBOX_OLHAR_SEGUNDOS
    assert e.olhar_dropbox() is True                                   # NF nova
    assert feitos == [("lista", True), ("emails", True)] and e.versao_tela == 1


def test_robo_avisa_o_painel_deste_pc(monkeypatch):
    import config
    import rede_local
    chamadas = []
    monkeypatch.setattr(config, "caminho_chave_google", lambda cfg: "chave.json")
    monkeypatch.setattr(rede_local, "segredo_da_chave", lambda caminho: b"segredo-de-teste")
    monkeypatch.setattr(rede_local, "perguntar", lambda segredo, end, acao, corpo, tempo=0: chamadas.append((end, acao, corpo)))
    conferente.avisar_paineis({}, "emails").join(5)
    assert chamadas == [(f"127.0.0.1:{rede_local.PORTA}", "novidade", {"o_que": "emails"})]


def test_robo_sem_painel_no_ar_nao_quebra(monkeypatch):
    import config
    import rede_local
    monkeypatch.setattr(config, "caminho_chave_google", lambda cfg: "chave.json")
    monkeypatch.setattr(rede_local, "segredo_da_chave", lambda caminho: b"segredo-de-teste")
    def recusa(*a, **k):
        raise ConnectionRefusedError("Painel fechado")
    monkeypatch.setattr(rede_local, "perguntar", recusa)
    conferente.avisar_paineis({}, "nf").join(5)                        # não levanta erro: a tela pega na volta normal


def test_publicado_do_espelho():
    esp = types.SimpleNamespace(estado={"publicado": "a", "publicado_textos": "b"})
    antes = conferente._publicado(esp)
    esp.estado["publicado"] = "c"
    assert conferente._publicado(esp) != antes
    assert conferente._publicado(types.SimpleNamespace()) == ("", "", "")


# ---------- velocidade 3: tela só com o que mudou ----------
def _servidor(estado_falso):
    import json as _json
    import urllib.request
    token = "tok-teste"
    srv = app_servidor.ServidorPainel(("127.0.0.1", 0), app_servidor.criar_handler(estado_falso, {}, token, [0.0],
                                                                                    envio=object()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path, versao=None):
        h = {"Host": f"127.0.0.1:{app_servidor.PORTA}", "X-Token": token}
        if versao:
            h["X-Versao"] = versao
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", headers=h)) as r:
            return _json.loads(r.read()), r.headers.get("X-Versao")
    return srv, get


def test_resposta_igual_a_que_a_tela_tem_vira_so_igual():
    emails = [{"id": "e1", "assunto": "NF"}]
    estado = types.SimpleNamespace(lista_emails=lambda: list(emails), marca_tela=lambda: "3.0.0")
    srv, get = _servidor(estado)
    try:
        j1, v1 = get("/api/emails")
        assert j1["emails"] == emails and v1
        j2, v2 = get("/api/emails", v1)
        assert j2 == {"__igual": True} and v2 == v1               # nada mudou: não manda de novo
        emails.append({"id": "e2", "assunto": "Outra"})
        j3, v3 = get("/api/emails", v1)
        assert len(j3["emails"]) == 2 and v3 != v1                 # mudou: manda tudo
        assert get("/api/emails", "versao-errada")[0]["emails"]    # versão que não bate: manda tudo
        assert get("/api/versao")[0] == {"v": "3.0.0"}
    finally:
        srv.shutdown()


def test_marca_da_tela_muda_com_leitura_e_com_envio_que_terminou():
    e = object.__new__(app_servidor.Estado)
    e.versao_tela = 1
    e.envio_nf = types.SimpleNamespace(locais={})
    m0 = e.marca_tela()
    e.envio_nf.locais["ENV-1"] = {"estado": "enviando"}
    m1 = e.marca_tela()
    e.envio_nf.locais["ENV-1"] = {"estado": "enviado"}
    m2 = e.marca_tela()
    e.versao_tela += 1
    assert len({m0, m1, m2, e.marca_tela()}) == 4


def test_igual_nao_conta_o_que_muda_sozinho_e_manda_a_hora_e_os_pcs():
    corpo = {"atualizado_em": "10:00", "pcs": [{"pc": "A", "visto": "10:00", "online": True}], "fila": [{"chave": "k", "dias": 0.1}]}
    estado = types.SimpleNamespace(lista_correio=lambda: corpo, marca_tela=lambda: "1.0.0")
    srv, get = _servidor(estado)
    try:
        j1, v1 = get("/api/correio")
        corpo.update(atualizado_em="10:15", pcs=[{"pc": "A", "visto": "10:15", "online": True}])
        corpo["fila"][0]["dias"] = 0.11
        j2, v2 = get("/api/correio", v1)
        assert j2 == {"__igual": True, "atualizado_em": "10:15", "pcs": [{"pc": "A", "visto": "10:15", "online": True}]}
        corpo["pcs"][0]["online"] = False                          # PC caiu: isso conta
        j3, v3 = get("/api/correio", v1)
        assert "fila" in j3 and v3 != v1
    finally:
        srv.shutdown()
