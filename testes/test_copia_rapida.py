"""Cópia rápida dos formulários (23/10/2026): vigia do Drive a cada 10 s, cópia só dos hotéis que mudaram, sem duplicar,
sem atrapalhar a rodada das 10 em 10 e sem comer a cota dos outros. Dados inventados."""
import datetime
import json
import threading
import time

import pytest

import app_servidor
import cota_google
import lock_execucao
import sincronizar
from vigia_formularios import VigiaFormularios

CAB = ["Carimbo de data/hora", "Endereço de e-mail", "Nome", "Enviado"]


# ---------- a vigia ----------
class Cena:
    def __init__(self, versoes):
        self.versoes = dict(versoes)
        self.copias, self.avisos, self.ciclo, self.trava_ocupada, self.mudam = [], 0, False, False, True
        self.falha = None

    def listar(self):
        return [{"id": i, "name": f"Solicitação Nota Fiscal ({i}) (respostas)", "version": v} for i, v in self.versoes.items()]

    def copiar(self, arquivos, ids):
        if self.falha:
            raise self.falha
        if self.trava_ocupada:
            return None
        self.copias.append(sorted(ids))
        return sorted(ids) if self.mudam else []

    def avisar(self):
        self.avisos += 1

    def vigia(self):
        return VigiaFormularios(self.listar, self.copiar, self.avisar, lambda: self.ciclo)


def test_primeira_volta_so_guarda_e_sem_mudanca_nao_copia():
    c = Cena({"LUXOR": "10", "BAHIA": "7"})
    v = c.vigia()
    assert v.volta() == [] and v.volta() == [] and c.copias == [] and c.avisos == 0


def test_versao_nova_copia_so_aquela_planilha_e_avisa_os_paineis():
    c = Cena({"LUXOR": "10", "BAHIA": "7"})
    v = c.vigia(); v.volta()
    c.versoes["BAHIA"] = "8"
    assert v.volta() == ["BAHIA"] and c.copias == [["BAHIA"]] and c.avisos == 1
    assert v.volta() == [] and len(c.copias) == 1          # a mesma versão não copia de novo


def test_mudanca_sem_linha_nova_nao_avisa():   # o robô marcou TRUE: lê, mas nada muda na Central
    c = Cena({"LUXOR": "10"}); c.mudam = False
    v = c.vigia(); v.volta()
    c.versoes["LUXOR"] = "11"
    assert v.volta() == [] and c.copias == [["LUXOR"]] and c.avisos == 0


def test_planilha_nova_na_pasta_entra():
    c = Cena({"LUXOR": "10"})
    v = c.vigia(); v.volta()
    c.versoes["NOVO"] = "1"
    assert v.volta() == ["NOVO"]


def test_rodada_das_10_em_10_rodando_espera_e_depois_copia():
    c = Cena({"LUXOR": "10"})
    v = c.vigia(); v.volta()
    c.versoes["LUXOR"] = "11"; c.ciclo = True
    assert v.volta() == [] and c.copias == []
    c.versoes["LUXOR"] = "12"                               # o robô marcou TRUE durante a rodada
    assert v.volta() == [] and c.copias == []
    c.ciclo = False
    assert v.volta() == ["LUXOR"] and c.copias == [["LUXOR"]]   # não perdeu o pedido que chegou na rodada


def test_trava_ocupada_ou_erro_tenta_na_proxima_volta():
    c = Cena({"LUXOR": "10"})
    v = c.vigia(); v.volta()
    c.versoes["LUXOR"] = "11"; c.trava_ocupada = True
    assert v.volta() == [] and v.pendentes == {"LUXOR"}
    c.trava_ocupada = False; c.falha = RuntimeError("cota")
    assert v.volta() == [] and v.pendentes == {"LUXOR"}
    c.falha = None
    assert v.volta() == ["LUXOR"] and v.pendentes == set()


# ---------- a cópia só dos hotéis que mudaram ----------
@pytest.fixture
def copia(cfg, tmp_path, monkeypatch):
    """sincronizar() de verdade, com Google e Drive falsos."""
    monkeypatch.setattr(sincronizar, "PASTA_ESTADO", tmp_path)
    monkeypatch.setattr(sincronizar, "carregar_config", lambda: cfg)
    monkeypatch.setattr(sincronizar, "caminho_chave_google", lambda c: "chave.json")
    hoteis = {"a": [CAB, ["22/10/2026 21:54:08", "marina@exemplo.com", "Marina Exemplo", ""]],
              "b": [CAB, ["22/10/2026 22:28:48", "lucas@exemplo.com", "Lucas Modelo", ""]]}
    central = {"Solicitação Nota Fiscal (LUXOR) (respostas)": [CAB], "Solicitação Nota Fiscal (BAHIA) (respostas)": [CAB]}
    lidos, gravados = [], {}

    class Backend:
        def __init__(self, *a, **k):
            self._cliente = object()

        def ler_abas(self, planilha, abas, faixas=None):
            return {a: [list(l) for l in central.get(a, [])] for a in abas}, {}

    import sheets
    monkeypatch.setattr(sheets, "BackendGoogle", Backend)
    monkeypatch.setattr(sincronizar, "PAUSA_ENTRE_LEITURAS", 0)
    monkeypatch.setattr(sincronizar, "_ler_planilha_hotel", lambda cli, a, c: (lidos.append(a["id"]) or "Respostas", hoteis[a["id"]]))
    monkeypatch.setattr(sincronizar, "_gravar_aba", lambda b, cli, cen, aba, linhas, criar: gravados.__setitem__(aba, linhas))
    monkeypatch.setattr(sincronizar, "marcar_true_nos_arquivos", lambda cli, plano: (0, []))
    monkeypatch.setattr(sincronizar.robo_antigo, "registrar_atividade", lambda *a, **k: None)
    mapa = {"cadastro": {"LUXOR": "LUXOR", "BAHIA": "BAHIA"}, "sem_hotel": [],
            "por_hotel": {"LUXOR": [{"id": "a", "name": "LUXOR", "modifiedTime": "t", "version": "2"}],
                          "BAHIA": [{"id": "b", "name": "BAHIA", "modifiedTime": "t", "version": "5"}]},
            "abas_central": list(central), "destino_do_hotel": {"LUXOR": "Solicitação Nota Fiscal (LUXOR) (respostas)",
                                                                  "BAHIA": "Solicitação Nota Fiscal (BAHIA) (respostas)"}}
    (tmp_path / sincronizar.VERSOES).write_text(json.dumps({"versoes": {"a": "1", "b": "5"}, "ultima_completa": "2026-10-23T08:00:00"}))
    return {"mapa": mapa, "lidos": lidos, "gravados": gravados, "central": central, "pasta": tmp_path}


def test_copia_so_os_hoteis_pedidos_mesmo_sem_versao_nova_e_guarda_a_versao(copia):
    rel, _, _ = sincronizar.sincronizar(gravar=True, so_hoteis={"BAHIA"}, mapa=copia["mapa"])
    assert copia["lidos"] == ["b"]                                       # BAHIA lido mesmo com a versão igual; LUXOR nem olhado
    assert list(copia["gravados"]) == ["Solicitação Nota Fiscal (BAHIA) (respostas)"]
    assert [r["hotel"] for r in rel if r.get("mudou")] == ["BAHIA"]
    guardado = json.loads((copia["pasta"] / sincronizar.VERSOES).read_text())
    assert guardado == {"versoes": {"a": "1", "b": "5"}, "ultima_completa": "2026-10-23T08:00:00"}   # a leitura completa não muda


def test_copiar_de_novo_nao_duplica(copia):
    sincronizar.sincronizar(gravar=True, so_hoteis={"LUXOR"}, mapa=copia["mapa"])
    aba = "Solicitação Nota Fiscal (LUXOR) (respostas)"
    copia["central"][aba] = copia["gravados"].pop(aba)                   # a Central agora tem a linha
    rel, _, _ = sincronizar.sincronizar(gravar=True, so_hoteis={"LUXOR"}, mapa=copia["mapa"])
    assert not copia["gravados"] and not any(r.get("mudou") for r in rel) and len(copia["central"][aba]) == 2


def test_marca_da_rodada_e_velha_nao_trava(tmp_path, monkeypatch):
    monkeypatch.setattr(sincronizar, "CICLO", tmp_path / "_ciclo_copia.txt")
    assert sincronizar.ciclo_rodando() is False
    agora = datetime.datetime(2026, 10, 23, 9, 0)
    (tmp_path / "_ciclo_copia.txt").write_text("2026-10-23T08:55:00")
    assert sincronizar.ciclo_rodando(agora) is True
    (tmp_path / "_ciclo_copia.txt").write_text("2026-10-23T08:30:00")     # rodada que morreu no meio
    assert sincronizar.ciclo_rodando(agora) is False


def test_rodada_marca_e_desmarca_mesmo_com_erro(tmp_path, monkeypatch):
    monkeypatch.setattr(sincronizar, "CICLO", tmp_path / "_ciclo_copia.txt")
    monkeypatch.setattr(sincronizar, "PASTA_ESTADO", tmp_path)
    vistos = []
    def falha():
        vistos.append(sincronizar.ciclo_rodando())
        raise RuntimeError("Google fora")
    monkeypatch.setattr(sincronizar, "_copiar_e_enviar", falha)
    with pytest.raises(RuntimeError):
        sincronizar.copiar_e_enviar()
    assert vistos == [True] and not (tmp_path / "_ciclo_copia.txt").exists()


# ---------- trava: a rodada espera a vigia em vez de pular ----------
def test_trava_espera_a_vigia_soltar(tmp_path, monkeypatch):
    monkeypatch.setattr(lock_execucao, "ARQUIVO_LOCK", str(tmp_path / "_execucao.lock"))
    monkeypatch.setattr(lock_execucao, "_ARQUIVO_MUTEX", str(tmp_path / "_execucao.lock.mutex"))
    assert lock_execucao.adquirir_lock()                                  # a vigia pegou
    assert lock_execucao.adquirir_lock() is False                         # sem esperar: desiste (como antes)
    threading.Timer(1.2, lock_execucao.liberar_lock).start()              # a vigia solta em ~1 s
    inicio = time.monotonic()
    assert lock_execucao.adquirir_lock(esperar=5) is True                 # a rodada esperou e pegou
    assert time.monotonic() - inicio < 4
    lock_execucao.liberar_lock()


def test_trava_que_nao_solta_desiste_no_prazo(tmp_path, monkeypatch):
    monkeypatch.setattr(lock_execucao, "ARQUIVO_LOCK", str(tmp_path / "_execucao.lock"))
    monkeypatch.setattr(lock_execucao, "_ARQUIVO_MUTEX", str(tmp_path / "_execucao.lock.mutex"))
    assert lock_execucao.adquirir_lock()
    inicio = time.monotonic()
    assert lock_execucao.adquirir_lock(esperar=2) is False
    assert 1.5 < time.monotonic() - inicio < 4
    lock_execucao.liberar_lock()


# ---------- cota: a vigia tem a fatia dela ----------
def test_vigia_conta_na_propria_fatia_e_o_resto_na_do_programa():
    vista = {}
    def linha():
        cota_google.usar_nesta_linha("vigia_formularios")
        vista["vigia"] = cota_google.atual().perfil
    t = threading.Thread(target=linha); t.start(); t.join()
    assert vista["vigia"] == "vigia_formularios" and cota_google.atual() is cota_google.COTA


def test_soma_das_fatias_com_a_vigia_fica_abaixo_de_60():
    P = cota_google.PERFIS
    for i in (0, 1):
        total = 3 * (P["painel"][i] + P["conferente"][i]) + P["painel"][i] + P["conferente_principal"][i] \
            + P["sincronizar"][i] + P["vigia_formularios"][i]
        assert total < cota_google.LIMITE_GOOGLE


# ---------- Painel: o aviso "formulario" relê as abas dos hotéis ----------
def test_aviso_de_formulario_rele_os_hoteis_na_hora():
    e = object.__new__(app_servidor.Estado)
    e.hoteis_lidos_em = 12345.0
    e._repassar_novidade = lambda corpo: None
    e.rede_novidade({"o_que": "formulario", "repassado": True})
    assert e.hoteis_lidos_em < 0 and e.acordar.is_set()
    e.hoteis_lidos_em = 99.0
    e.rede_novidade({"o_que": "nf", "repassado": True})
    assert e.hoteis_lidos_em == 99.0
