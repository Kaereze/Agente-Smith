"""Identidade do PC (src/identidade.py): votação contas do Outlook × Cadastro_Hoteis."""
import json
import socket
import types

import identidade
from identidade import resolver

CAD = [(f"H{i}", f"nf{i}@joao.com", "João") for i in range(12)] + [(f"C{i}", f"nf{i}@clara.com", "Clara") for i in range(8)]


def _detectar(tmp_path, monkeypatch, contas, maquina_antes=None):
    caminho = tmp_path / "maquina.json"
    if maquina_antes is not None:
        caminho.write_text(json.dumps(maquina_antes), encoding="utf-8")
    monkeypatch.setattr(identidade, "CAMINHO_MAQUINA", caminho)
    ns = types.SimpleNamespace(Accounts=[types.SimpleNamespace(SmtpAddress=c) for c in contas])
    cadastro = [["Hotel", "E-mail", "Agente"]] + [list(l) for l in CAD]
    backend = types.SimpleNamespace(ler_abas=lambda _id, abas: ({abas[0]: cadastro}, {}))
    cfg = {"aba_cadastro_hoteis": "Cadastro_Hoteis", "planilha_central_id": "x"}
    return identidade.detectar(cfg, ns, backend), json.loads(caminho.read_text(encoding="utf-8"))


def test_pc_do_joao():
    agente, conf, _, _ = resolver([f"nf{i}@joao.com" for i in range(12)] + ["pessoal@gmail.com"], CAD)
    assert agente == "João" and conf == 100


def test_outlook_ainda_carregando_recusa_e_tenta_de_novo():
    agente, _, _, retentavel = resolver(["nf1@joao.com", "nf2@joao.com"], CAD)
    assert agente is None and retentavel


def test_pc_com_contas_de_dois_agentes_nao_e_atribuido():
    agente, _, motivo, retentavel = resolver([f"nf{i}@joao.com" for i in range(8)] + [f"nf{i}@clara.com" for i in range(6)], CAD)
    assert agente is None and not retentavel and "mais de um agente" in motivo


def test_maquina_json_copiado_do_joao_vira_clara_pelas_contas(tmp_path, monkeypatch):
    """estado\\ copiada do PC do João pro da Clara: as contas do Outlook decidem."""
    dados, gravado = _detectar(tmp_path, monkeypatch, [f"nf{i}@clara.com" for i in range(8)],
                               {"agente": "João", "confianca": 100, "contas": 18})
    assert dados["agente"] == gravado["agente"] == "Clara"
    assert gravado["pc"] == socket.gethostname() and "conflito" not in gravado


def test_contas_ambiguas_mantem_o_que_ja_sabia(tmp_path, monkeypatch):
    contas = [f"nf{i}@joao.com" for i in range(8)] + [f"nf{i}@clara.com" for i in range(6)]
    dados, gravado = _detectar(tmp_path, monkeypatch, contas, {"agente": "Clara", "pc": socket.gethostname()})
    assert dados["agente"] == gravado["agente"] == "Clara"


def test_maquina_json_de_outro_pc_e_ignorado(tmp_path, monkeypatch):
    monkeypatch.setattr(identidade, "CAMINHO_MAQUINA", tmp_path / "maquina.json")
    (tmp_path / "maquina.json").write_text('{"agente": "João", "pc": "OUTRO-PC"}', encoding="utf-8")
    assert identidade.ler() == {}
    (tmp_path / "maquina.json").write_text(json.dumps({"agente": "João", "pc": socket.gethostname()}), encoding="utf-8")
    assert identidade.ler()["agente"] == "João"
