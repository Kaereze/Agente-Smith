"""Modo demonstração (PC de casa): sobe com dados fictícios e as ações só fingem."""
import demo
from app_servidor import Estado


def _estado(cfg, tmp_path, monkeypatch):
    import app_servidor
    monkeypatch.setattr(app_servidor, "CAMINHO_CACHE", tmp_path / "cache_demo.pkl")
    b = demo.BackendDemo()
    e = Estado(b, demo.configurar_cfg(cfg))
    demo.preparar(e, b)
    e.atualizar()
    return e, b


def test_demo_sobe_com_pedidos_e_emails_ficticios(cfg, tmp_path, monkeypatch):
    e, _ = _estado(cfg, tmp_path, monkeypatch)
    assert e.erro == "" and len(e.solicitacoes) > 50
    c = e.lista_correio()
    assert c["emails"] and c["conversas"] and c["enviados"]
    assert {p["agente"] for p in c["pcs"] if not p["online"]} == {demo.DESLIGADO}
    assert not any(e2["de"].endswith("@redeandrade.com.br") for e2 in c["emails"])   # hóspedes inventados


def test_demo_busca_texto_e_acoes_so_fingem(cfg, tmp_path, monkeypatch):
    e, b = _estado(cfg, tmp_path, monkeypatch)
    alvo = e.lista_correio()["emails"][0]
    r = e.buscar_outlook(alvo["de"].split("@")[0])
    assert any(x["de"] == alvo["de"] for x in r["resultados"])
    assert e.texto_email(alvo["id"])["texto"]
    assert e.excluir_email(alvo["id"], "João")["ok"]
    e.atualizar()
    assert alvo["id"] not in {x["id"] for x in e.lista_correio()["emails"]}
