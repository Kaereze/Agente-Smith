"""Registro de acessos (LGPD, 08/11/2026): quem abriu o quê, sem nome, CPF, e-mail nem texto do hóspede."""
import datetime
import json

from privacidade import acessos
from sistema import armazem


def _pasta(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)


def test_registra_quem_quando_pc_tipo_e_so_uma_referencia_do_item(monkeypatch, tmp_path):
    _pasta(monkeypatch, tmp_path)
    agora = datetime.datetime(2026, 11, 8, 10, 30)
    assert acessos.registrar("João", "PC-A", "email", "ID-SECRETO-DO-EMAIL-123", "BAHIA", agora=agora)
    linha = json.loads((tmp_path / "acessos" / "2026-11.jsonl").read_text(encoding="utf-8").strip())
    assert linha["agente"] == "João" and linha["pc"] == "PC-A" and linha["tipo"] == "email" and linha["quando"] == "2026-11-08T10:30:00"
    assert linha["ref"] == acessos.referencia("ID-SECRETO-DO-EMAIL-123") and len(linha["ref"]) == 10
    assert "SECRETO" not in json.dumps(linha) and "@" not in json.dumps(linha)


def test_tipo_desconhecido_nao_grava(monkeypatch, tmp_path):
    _pasta(monkeypatch, tmp_path)
    assert acessos.registrar("João", "PC-A", "senha") is False
    assert not (tmp_path / "acessos").exists()


def test_resumo_conta_por_operador_e_tipo_e_ignora_linha_cortada(monkeypatch, tmp_path):
    _pasta(monkeypatch, tmp_path)
    agora = datetime.datetime(2026, 11, 8, 9, 0)
    for ag, tipo in [("João", "email"), ("João", "email"), ("João", "ficha"), ("Clara", "anexo")]:
        acessos.registrar(ag, "PC", tipo, "x", agora=agora)
    with open(tmp_path / "acessos" / "2026-11.jsonl", "a", encoding="utf-8") as f:
        f.write('{"quando": "2026-11-08T09:')   # queda de energia no meio da linha
    assert acessos.resumo("2026-11") == {"Clara": {"anexo": 1}, "João": {"email": 2, "ficha": 1}}


def test_limpar_apaga_so_o_que_passou_de_12_meses(monkeypatch, tmp_path):
    _pasta(monkeypatch, tmp_path)
    pasta = tmp_path / "acessos"; pasta.mkdir()
    for mes in ("2025-09", "2025-10", "2025-11", "2026-11"):
        (pasta / f"{mes}.jsonl").write_text("{}\n", encoding="utf-8")
    assert acessos.limpar(datetime.date(2026, 11, 8)) == 2          # 2025-09 e 2025-10 saem; 2025-11 (12 meses) fica
    assert sorted(f.stem for f in pasta.glob("*.jsonl")) == ["2025-11", "2026-11"]


def test_falha_ao_gravar_nao_derruba_a_leitura(monkeypatch, tmp_path):
    arq = tmp_path / "acessos"; arq.write_text("sou um arquivo, não uma pasta", encoding="utf-8")
    _pasta(monkeypatch, tmp_path)
    assert acessos.registrar("João", "PC", "email", "x") is False


def test_rotas_anotam_texto_anexo_e_ficha_mas_nao_erro(monkeypatch):
    from painel import rotas_api
    fonte = open(rotas_api.__file__, encoding="utf-8").read()
    assert '_vendo(c, "email"' in fonte and '_vendo(c, "anexo"' in fonte and '"/api/acesso"' in fonte
    chamadas = []
    monkeypatch.setattr(rotas_api.acessos, "registrar", lambda *a, **k: chamadas.append(a) or True)
    import types
    c = types.SimpleNamespace(agente=lambda: "João", pc="PC-A")
    assert rotas_api._vendo(c, "email", "id1", {"texto": "ok"}) == {"texto": "ok"} and len(chamadas) == 1
    rotas_api._vendo(c, "email", "id2", {"erro": "sem rede"})
    assert len(chamadas) == 1   # erro não conta como acesso
