"""Enviar/Receber todas (27/10/2026): pedido aos 4 PCs, estimativa pelo histórico, falhas e o gancho de ação longa."""
import json
import time
from pathlib import Path

import enviar_receber as er

UI = Path(__file__).resolve().parent.parent / "app_ui"
CORREIO = (UI / "correio.js").read_text(encoding="utf-8")
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")

PCS = [{"pc": "PC-J", "agente": "João", "online": True, "rede": "10.0.0.1:8766"},
       {"pc": "PC-C", "agente": "Clara", "online": True, "rede": "10.0.0.2:8766"},
       {"pc": "PC-K", "agente": "Cristian", "online": True, "rede": "10.0.0.3:8766"},
       {"pc": "PC-B", "agente": "Bernardo", "online": False, "rede": ""}]


def servico(tmp_path, respostas, pcs=PCS, avisos=None):
    chamadas = []

    def remoto(pc, end):
        chamadas.append(pc)
        r = respostas[pc]
        if isinstance(r, Exception):
            raise r
        time.sleep(r.pop("_dorme", 0))
        return r
    s = er.EnviarReceber("PC-J", lambda: respostas["PC-J"], remoto, lambda: pcs, tmp_path / "t.json",
                         ao_terminar=(avisos.append if avisos is not None else None))
    return s, chamadas


def esperar_fim(s, id_):
    for _ in range(200):
        v = s.status(id_)
        if v["fim"]:
            return v
        time.sleep(0.02)
    return s.status(id_)


def test_pede_a_todos_os_online_e_marca_o_desligado(tmp_path):
    avisos = []
    s, chamadas = servico(tmp_path, {"PC-J": {"ok": True, "segundos": 3.0, "saiu": 0, "presos": 0},
                                     "PC-C": {"ok": True, "segundos": 5.0, "saiu": 2, "presos": 0},
                                     "PC-K": {"ok": True, "segundos": 9.0, "saiu": 15, "presos": 0}}, avisos=avisos)
    v = esperar_fim(s, s.iniciar("João")["id"])
    assert sorted(chamadas) == ["PC-C", "PC-K"]                           # o PC-J é local, o PC-B está desligado
    estados = {p["agente"]: (p["estado"], p["res"]) for p in v["pcs"]}
    assert estados["Bernardo"] == ("falha", "desligado")
    assert estados["Cristian"][0] == "feito" and "15 saíram" in estados["Cristian"][1]
    assert v["fim"] and v["feitos"] == 4 and v["falhas"] == ["Bernardo: desligado"] and v["progresso"] == 1.0
    for _ in range(100):                                                   # o aviso de cada PC chega logo depois de ele terminar
        if len(avisos) == 3:
            break
        time.sleep(0.02)
    assert sorted(avisos) == ["PC-C", "PC-J", "PC-K"]                     # a tela é avisada a cada PC que termina


def test_falhas_de_cada_tipo_nao_travam_o_resto(tmp_path):
    s, _ = servico(tmp_path, {"PC-J": {"ok": True, "segundos": 1, "saiu": 0, "presos": 0},
                              "PC-C": {"erro": "Outlook em \u201cTrabalhar Offline\u201d"}, "PC-K": TimeoutError("lento")})
    v = esperar_fim(s, s.iniciar()["id"])
    assert v["fim"] and v["feitos"] == 4
    assert any("Trabalhar Offline" in f for f in v["falhas"]) and any(f.startswith("Cristian: falhou") for f in v["falhas"])


def test_presos_viram_aviso_e_nao_erro(tmp_path):
    s, _ = servico(tmp_path, {"PC-J": {"ok": True, "segundos": 2, "saiu": 0, "presos": 0}, "PC-C": {"ok": True, "segundos": 2, "saiu": 0, "presos": 0},
                              "PC-K": {"ok": True, "segundos": 9, "saiu": 3, "presos": 12}})
    v = esperar_fim(s, s.iniciar()["id"])
    assert v["avisos"] == ["Cristian: 9 s · 3 saíram · 12 continuam presos"] and not any("Cristian" in f for f in v["falhas"])


def test_estimativa_vem_da_mediana_dos_ultimos_tempos(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps({"PC-C": [4.0, 6.0, 5.0], "PC-K": [10.0]}))
    s, _ = servico(tmp_path, {"PC-J": {"_dorme": 0.3, "ok": True, "segundos": 1, "saiu": 0, "presos": 0},
                              "PC-C": {"_dorme": 0.3, "ok": True, "segundos": 5, "saiu": 0, "presos": 0},
                              "PC-K": {"_dorme": 0.3, "ok": True, "segundos": 10, "saiu": 0, "presos": 0}})
    v = s.iniciar("João")
    assert 8 <= v["eta"] <= 10 and not v["fim"] and 0 <= v["progresso"] < 1      # o mais lento (10 s) manda
    esperar_fim(s, v["id"])
    assert json.loads((tmp_path / "t.json").read_text())["PC-C"][-1] == 5.0     # o tempo novo entra no histórico


def test_um_pedido_por_vez_e_intervalo_entre_pedidos(tmp_path):
    s, _ = servico(tmp_path, {"PC-J": {"ok": True, "segundos": 1, "saiu": 0, "presos": 0},
                              "PC-C": {"_dorme": 0.4, "ok": True, "segundos": 1, "saiu": 0, "presos": 0}, "PC-K": {"ok": True, "segundos": 1, "saiu": 0, "presos": 0}})
    a = s.iniciar("João")
    assert s.iniciar("Clara")["id"] == a["id"]                                   # já tem um rodando: devolve o mesmo
    esperar_fim(s, a["id"])
    assert "Acabou de rodar" in s.iniciar("João")["erro"]


def test_pedido_desconhecido():
    s = er.EnviarReceber("PC-J", lambda: {}, lambda *a: {}, lambda: [], Path("x.json"))
    assert s.status("nada")["erro"]


# ---------- o Outlook deste PC ----------
class Pasta:
    def __init__(self, contagens):
        self.contagens, self.EntryID = list(contagens), "pasta1"

    @property
    def Items(self):
        class I:
            Count = self.contagens.pop(0) if len(self.contagens) > 1 else self.contagens[0]
        return I


class Ns:
    def __init__(self, contagens, offline=False):
        self.Offline, self.pasta, self.Accounts, self.chamou = offline, Pasta(contagens), [], 0

    def GetDefaultFolder(self, _n):
        return self.pasta

    def SendAndReceive(self, _mostrar):
        self.chamou += 1


def test_rodar_aqui_espera_a_caixa_de_saida_esvaziar():
    ns = Ns([15, 15, 9, 3, 0])
    r = er.rodar_aqui(ns, dormir=lambda s: None, relogio=iter([0, 0.5, 1, 1.5, 2.5, 3, 3.5, 4, 5, 6, 7]).__next__)
    assert ns.chamou == 1 and r["ok"] and r["saiu"] == 15 and r["presos"] == 0


def test_rodar_aqui_nao_espera_para_sempre_se_a_caixa_nao_esvazia():
    ns = Ns([15])
    t = iter(range(0, 100))
    r = er.rodar_aqui(ns, dormir=lambda s: None, relogio=lambda: next(t))
    assert r["ok"] and r["presos"] == 15 and r["saiu"] == 0 and r["segundos"] < 25


def test_rodar_aqui_em_trabalhar_offline_diz_o_motivo():
    ns = Ns([1], offline=True)
    r = er.rodar_aqui(ns, dormir=lambda s: None)
    assert "Trabalhar Offline" in r["erro"] and ns.chamou == 0                   # nem tenta


# ---------- a tela ----------
def test_botao_chama_o_pedido_aos_pcs_e_nao_so_recarrega():
    assert "if (d.olAcao === \"sync\") enviarReceberTodas();" in CORREIO
    assert "/api/enviar_receber/status?id=" in CORREIO and CORREIO.count("pintarSync();") >= 4
    assert "Relendo as caixas dos 4 PCs" not in CORREIO


def test_gancho_de_acao_longa_avisa_depois_de_3_s_e_o_api_liga_sozinho():
    assert "LIMITE_ACAO_LONGA_MS = 3000" in PAINEL and "painel:acao-longa" in PAINEL and "painel:acao-longa-fim" in PAINEL
    assert "const longa = corpo ? acaoLonga(path) : null;" in HTML and HTML.count("longa?.fim(") == 3


def test_servidor_so_atende_pelo_painel_deste_pc_e_pela_rede_assinada():
    import app_servidor
    fonte = Path(app_servidor.__file__).read_text(encoding="utf-8")
    assert '"enviar_receber": estado.rede_enviar_receber' in fonte and 'path == "/api/enviar_receber"' in fonte
